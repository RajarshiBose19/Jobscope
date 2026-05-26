"""Pydantic models for the Gemini response contract."""
from typing import Literal, Optional
from pydantic import BaseModel, Field

RedFlagKind = Literal[
    "staffing_recruiting", "experience_mismatch", "skill_domain_mismatch",
    "visa_or_citizenship", "salary_below_expected", "vague_jd",
]

class RedFlag(BaseModel):
    kind: RedFlagKind
    text: str

class JDSkill(BaseModel):
    canonical: str
    as_written: str
    kind: Literal["required", "nice_to_have"]

class JobAnalysis(BaseModel):
    fit_score: int = Field(ge=0, le=100)
    fit_rationale: str
    experience_verdict: Literal["in_range", "under", "over", "way_over"]
    experience_min_years: Optional[int] = None
    experience_max_years: Optional[int] = None
    skills: list[JDSkill]
    red_flags: list[RedFlag] = []
    jd_quality: Literal["well_written", "average", "vague"]
    recommendation: str
    resume_tailoring: str
    salary_min_lpa: Optional[float] = None
    salary_max_lpa: Optional[float] = None
