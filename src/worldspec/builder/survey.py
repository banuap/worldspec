"""Repository survey — turn a GitHub URL (or local path) into a structured
summary the model builder can reason over.

This is the *ingestion* half of a source adapter: it clones/reads the repo,
classifies the stack, inventories source units, and samples representative code.
Model generation (heuristic or LLM) happens in :mod:`worldspec.builder.build`.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# Extension -> language
_LANG = {
    ".java": "java", ".kt": "kotlin", ".py": "python", ".js": "javascript",
    ".ts": "typescript", ".tsx": "typescript", ".go": "go", ".rb": "ruby",
    ".cs": "csharp", ".cbl": "cobol", ".cob": "cobol", ".cpy": "cobol-copybook",
    ".jcl": "jcl", ".sql": "sql", ".c": "c", ".cpp": "cpp", ".rs": "rust",
}
_IGNORE_DIRS = {".git", "node_modules", "build", "out", "dist", "target",
                ".idea", ".vscode", "__pycache__", ".venv", "venv", "vendor"}
_MAX_FILES = 6000
_MAX_UNITS = 120
_MAX_SAMPLE_BYTES = 40_000
_MAX_SAMPLES = 30
_MAX_FILELIST = 300

# Signals that seed domain-appropriate invariants/relationships.
_SIGNALS = {
    "database": r"(EXEC\s+SQL|jdbc:|snowflake|\bSELECT\b.+\bFROM\b|CREATE\s+TABLE|read_csv|to_sql|@Entity|@Table)",
    "http_api": r"(https?://|RestTemplate|HttpClient|requests\.|fetch\(|axios|@RestController|FastAPI|flask|express)",
    "auth": r"(password|login|authenticate|\btoken\b|oauth|jwt|credential|secret)",
    "file_io": r"(FileReader|FileWriter|open\(|read_csv|to_csv|\.write\(|PrintWriter|BufferedReader)",
    "scheduling": r"(cron|schedule|\bTimer\b|@Scheduled|batch|JCL|airflow|dag)",
    "messaging": r"(kafka|rabbitmq|sqs|pubsub|@KafkaListener|producer|consumer)",
    "money": r"(amount|balance|price|spend|revenue|cost|payment|invoice|ledger)",
}
_EXTERNALS = r"\b(snowflake|kafka|s3|redis|postgres|postgresql|mysql|oracle|mongodb|salesforce|stripe|bigquery|databricks)\b"


@dataclass
class SourceUnit:
    path: str          # repo-relative
    language: str
    name: str          # class / program / module name
    size: int


@dataclass
class Survey:
    source: str
    languages: dict[str, int] = field(default_factory=dict)  # language -> file count
    stack: str = "generic"
    units: list[SourceUnit] = field(default_factory=list)
    file_count: int = 0
    has_tests: bool = False
    samples: dict[str, str] = field(default_factory=dict)     # path -> snippet
    files: list[str] = field(default_factory=list)            # code file inventory
    signals: dict[str, bool] = field(default_factory=dict)    # detected concerns
    externals: list[str] = field(default_factory=list)        # external systems

    def summary(self) -> dict:
        return {
            "source": self.source,
            "stack": self.stack,
            "languages": self.languages,
            "fileCount": self.file_count,
            "unitCount": len(self.units),
            "hasTests": self.has_tests,
            "units": [u.name for u in self.units],
            "signals": sorted(k for k, v in self.signals.items() if v),
            "externals": self.externals,
        }


def _clone(url: str) -> tuple[Path, Optional[str]]:
    """Shallow-clone ``url`` into a temp dir. Returns (path, tempdir_to_cleanup)."""
    tmp = tempfile.mkdtemp(prefix="worldspec-build-")
    try:
        subprocess.run(
            ["git", "clone", "--depth", "1", url, tmp],
            check=True, capture_output=True, text=True, timeout=120,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        shutil.rmtree(tmp, ignore_errors=True)
        detail = getattr(exc, "stderr", "") or str(exc)
        raise SurveyError(f"git clone failed for {url}: {detail.strip()[:300]}")
    return Path(tmp), tmp


class SurveyError(Exception):
    code = "WS-BLD-0001"


def survey_repo(source: str) -> tuple[Survey, Optional[str]]:
    """Survey a git URL or local path. Returns (survey, tempdir_or_None)."""
    cleanup: Optional[str] = None
    if re.match(r"^(https?://|git@)", source) or source.endswith(".git"):
        root, cleanup = _clone(source)
    else:
        root = Path(source)
        if not root.exists():
            raise SurveyError(f"path not found: {source}")

    survey = Survey(source=source)
    seen_units: set[str] = set()
    files_walked = 0

    for path in sorted(root.rglob("*")):
        if any(part in _IGNORE_DIRS for part in path.parts):
            continue
        if not path.is_file():
            continue
        files_walked += 1
        if files_walked > _MAX_FILES:
            break
        rel = path.relative_to(root).as_posix()
        lang = _LANG.get(path.suffix.lower())
        if lang is None:
            continue
        survey.file_count += 1
        survey.languages[lang] = survey.languages.get(lang, 0) + 1
        if len(survey.files) < _MAX_FILELIST:
            survey.files.append(rel)
        if re.search(r"(^|/)(test|tests|spec)s?(/|_|\.)", rel, re.I):
            survey.has_tests = True
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        # detect domain signals + external systems
        for concern, pattern in _SIGNALS.items():
            if not survey.signals.get(concern) and re.search(pattern, text, re.I):
                survey.signals[concern] = True
        for ext in re.findall(_EXTERNALS, text, re.I):
            ext = ext.lower()
            if ext not in survey.externals:
                survey.externals.append(ext)
        # record a unit name for code files
        name = _unit_name(path, text, lang)
        if name and name not in seen_units and len(survey.units) < _MAX_UNITS:
            seen_units.add(name)
            survey.units.append(SourceUnit(path=rel, language=lang, name=name, size=len(text)))
        if len(survey.samples) < _MAX_SAMPLES and len(text) < _MAX_SAMPLE_BYTES:
            survey.samples[rel] = text[:_MAX_SAMPLE_BYTES]

    survey.stack = _detect_stack(survey)
    return survey, cleanup


def cleanup(tempdir: Optional[str]) -> None:
    if tempdir:
        shutil.rmtree(tempdir, ignore_errors=True)


def _unit_name(path: Path, text: str, lang: str) -> Optional[str]:
    if lang == "cobol":
        m = re.search(r"PROGRAM-ID\.\s*([\w-]+)", text, re.I)
        return m.group(1) if m else path.stem
    if lang in ("java", "kotlin", "csharp"):
        m = re.search(r"\b(?:public\s+)?(?:final\s+|abstract\s+)?class\s+(\w+)", text)
        return m.group(1) if m else path.stem
    return path.stem


def _detect_stack(survey: Survey) -> str:
    langs = survey.languages
    if langs.get("java"):
        swing = any("javax.swing" in s for s in survey.samples.values())
        return "java-swing" if swing else "java"
    if langs.get("cobol") or langs.get("jcl"):
        return "cobol"
    if langs.get("python"):
        return "python"
    if langs.get("typescript") or langs.get("javascript"):
        return "node"
    return "generic"
