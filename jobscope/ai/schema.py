from typing import Literal, Optional
from pydantic import BaseModel, Field

RedFlagKind = Literal[
    "staffing_recruiting", "experience_mismatch", "skill_domain_mismatch",
    "visa_or_citizenship", "vague_jd", "bond_commitment",
    "notice_period_mismatch",
]

class RedFlag(BaseModel):
    kind: RedFlagKind
    text: str

class JDSkill(BaseModel):
    canonical: str
    as_written: str
    kind: Literal["required", "nice_to_have"]
    match: Literal["matched", "partial", "missing"]

class JobAnalysis(BaseModel):
    fit_score: int = Field(ge=0, le=100)
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
    action_required: Optional[str] = None
