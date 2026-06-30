"""WorldSpec model builder — turn a repository into a WorldSpec model.

`build_model` surveys a repo (git URL or local path), generates a model
(heuristic by default; LLM-tailored when configured), and validates it with the
compiler before returning.
"""

from worldspec.builder.build import BuildResult, build_model
from worldspec.builder.survey import SurveyError, survey_repo

__all__ = ["BuildResult", "build_model", "survey_repo", "SurveyError"]
