import pytest
from pydantic import ValidationError
from jobscope.ai.schema import JobAnalysis

GOOD = {
    "fit_score": 70, "fit_rationale": "ok",
    "experience_verdict": "in_range",
    "experience_min_years": 2, "experience_max_years": 4,
    "skills": [{"canonical": "python", "as_written": "Python", "kind": "required"}],
    "red_flags": [],
    "jd_quality": "average",
    "recommendation": "decent fit",
    "resume_tailoring": "emphasize python",
    "salary_min_lpa": None, "salary_max_lpa": None,
}

def test_accepts_valid_payload():
    a = JobAnalysis.model_validate(GOOD)
    assert a.fit_score == 70

def test_rejects_out_of_range_fit_score():
    bad = {**GOOD, "fit_score": 120}
    with pytest.raises(ValidationError):
        JobAnalysis.model_validate(bad)

def test_rejects_unknown_red_flag_kind():
    bad = {**GOOD, "red_flags": [{"kind": "bogus", "text": "x"}]}
    with pytest.raises(ValidationError):
        JobAnalysis.model_validate(bad)

def test_rejects_unknown_skill_kind():
    bad = {**GOOD, "skills": [{"canonical": "x", "as_written": "X", "kind": "matched"}]}
    with pytest.raises(ValidationError):
        JobAnalysis.model_validate(bad)
