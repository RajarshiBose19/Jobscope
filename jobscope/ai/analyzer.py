from __future__ import annotations
import json
import time
from collections import Counter
from typing import Tuple
from pydantic import ValidationError
from jobscope.ai.client import GeminiClient, AnalysisFailure
from jobscope.ai.prompts import build_system, build_user
from jobscope.ai.schema import JobAnalysis
from jobscope.utils.logging import get_logger

log = get_logger("ai.analyzer")


def analyze(
    client: GeminiClient,
    *,
    profile: dict,
    skills_canonical: list[str],
    job: dict,
) -> Tuple[JobAnalysis, str, int]:
    system = build_system(profile, skills_canonical)
    user = build_user(job)
    last_err: Exception | None = None
    for attempt in (1, 2):
        t0 = time.monotonic()
        result = client.generate_json(system=system, user=user, response_schema=JobAnalysis)
        latency_ms = int((time.monotonic() - t0) * 1000)
        try:
            parsed = JobAnalysis.model_validate_json(result.text)
            req_dist = Counter(s.match for s in parsed.skills if s.kind == "required")
            nice_dist = Counter(s.match for s in parsed.skills if s.kind == "nice_to_have")
            log.info("skill_match_distribution",
                     extra={"required": dict(req_dist),
                            "nice_to_have": dict(nice_dist),
                            "fit_score": parsed.fit_score})
            return parsed, result.text, latency_ms
        except (ValidationError, json.JSONDecodeError) as e:
            last_err = e
            log.warning("analysis_validation_failed",
                        extra={"attempt": attempt, "err": str(e)[:200]})
            if attempt == 2:
                break
    raise AnalysisFailure(f"validation failed twice: {last_err}")
