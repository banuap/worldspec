import os
import sys
from pathlib import Path

# Tests must be deterministic and offline: never load a real .env / call an LLM.
os.environ["WORLDSPEC_NO_DOTENV"] = "1"
for _k in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "ANTHROPIC_API_KEY", "WORLDSPEC_LLM_PROVIDER"):
    os.environ.pop(_k, None)

# Ensure the src/ layout is importable even without an editable install.
SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

MODELS_DIR = Path(__file__).resolve().parents[1] / "models"
