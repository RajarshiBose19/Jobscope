"""Single-job analysis with one retry on parse/validation failure."""
from __future__ import annotations
import json
import time
from typing import Tuple
from pydantic import ValidationError
from jobscope.ai.client import GeminiClient, AnalysisFailure
from jobscope.ai.prompts import build_system, build_user
from jobscope.ai.schema import JobAnalysis

def analyze(
    client: GeminiClient,
    *,
    profile: dict,
    skills_canonical: list[str],
    job: dict,
) -> Tuple[JobAnalysis, str, int]:
    """Return (parsed, raw_json_text, latency_ms). Raises AnalysisFailure on hard fail."""
    system = build_system(profile, skills_canonical)
    user = build_user(job)
    last_err: Exception | None = None
    for attempt in (1, 2):
        t0 = time.monotonic()
        result = client.generate_json(system=system, user=user, response_schema=JobAnalysis)
        latency_ms = int((time.monotonic() - t0) * 1000)
        try:
            parsed = JobAnalysis.model_validate_json(result.text)
            return parsed, result.text, latency_ms
        except (ValidationError, json.JSONDecodeError) as e:
            last_err = e
            if attempt == 2:
                break
    raise AnalysisFailure(f"validation failed twice: {last_err}")
