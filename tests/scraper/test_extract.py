import pytest
from jobscope.scraper.extract import extract_years

@pytest.mark.parametrize("text, expected", [
    ("3-5 years of experience", (3, 5)),
    ("5+ years required", (5, None)),
    ("Minimum 4 years", (4, None)),
    ("2 to 4 years", (2, 4)),
    ("No experience required", (0, 0)),
    ("Fresh graduate", (0, 0)),
    ("0-2 years", (0, 2)),
    ("at least 7 years", (7, None)),
    ("",                       (None, None)),
    ("nothing relevant here", (None, None)),
])
def test_extract_years(text, expected):
    assert extract_years(text) == expected
