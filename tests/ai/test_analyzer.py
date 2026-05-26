import json
from unittest.mock import MagicMock
import pytest
from jobscope.ai.analyzer import analyze
from jobscope.ai.client import AnalysisFailure

VALID_JSON = json.dumps({
    "fit_score": 65, "fit_rationale": "decent",
    "experience_verdict": "in_range",
    "experience_min_years": 2, "experience_max_years": 4,
    "skills": [{"canonical": "python", "as_written": "Python", "kind": "required"}],
    "red_flags": [],
    "jd_quality": "average",
    "recommendation": "ok",
    "resume_tailoring": "emphasize python",
    "salary_min_lpa": None, "salary_max_lpa": None,
})

def _client(text_seq):
    c = MagicMock()
    results = [MagicMock(text=t) for t in text_seq]
    c.generate_json.side_effect = results
    return c

def test_analyze_returns_parsed_and_raw():
    c = _client([VALID_JSON])
    profile = {"full_name": "x"}; canon = ["python"]
    job = {"title": "T"}
    parsed, raw, latency = analyze(c, profile=profile, skills_canonical=canon, job=job)
    assert parsed.fit_score == 65
    assert raw == VALID_JSON
    assert latency >= 0

def test_analyze_retries_once_on_invalid_json():
    c = _client(["not json", VALID_JSON])
    parsed, _, _ = analyze(c, profile={}, skills_canonical=[], job={})
    assert parsed.fit_score == 65
    assert c.generate_json.call_count == 2

def test_analyze_fails_after_two_invalid_responses():
    c = _client(["not json", "still not"])
    with pytest.raises(AnalysisFailure):
        analyze(c, profile={}, skills_canonical=[], job={})
