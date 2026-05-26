from pathlib import Path
from jobscope.profile.parse_resume import extract_text

def test_extract_text_returns_nonempty_for_real_resume():
    pdf = Path("projects/jobscope/resume.pdf")
    if not pdf.exists():
        import pytest; pytest.skip("resume.pdf not present")
    text = extract_text(pdf)
    assert len(text) > 500
    assert "Rajarshi" in text or "Bose" in text
