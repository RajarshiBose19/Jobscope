"""LinkedIn DOM scraping + JD text parsing."""
from __future__ import annotations
import re
import time
from typing import Optional
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from jobscope.scraper._clickers import wait_for, text_or_empty, attr_or_empty
from jobscope.utils.logging import get_logger

log = get_logger("scraper.extract")

# ---------- years-of-experience parsing ----------

_RX_RANGE = re.compile(r"(\d{1,2})\s*(?:-|to|–|—)\s*(\d{1,2})\s*(?:\+)?\s*(?:years?|yrs?)", re.I)
_RX_PLUS  = re.compile(r"(\d{1,2})\s*\+\s*(?:years?|yrs?)", re.I)
_RX_AT_LEAST = re.compile(r"(?:at\s*least|minimum|min\.?)\s*(\d{1,2})\s*(?:years?|yrs?)", re.I)
_RX_NUM   = re.compile(r"\b(\d{1,2})\s*(?:years?|yrs?)\b", re.I)
_RX_NONE  = re.compile(r"(?:\bno\s+experience\b|\bfresher\b|\bfresh\s+grad\w*|\bentry[-\s]level\b)", re.I)

def extract_years(text: str) -> tuple[Optional[int], Optional[int]]:
    """Return (min_years, max_years). (None, None) if unparseable."""
    if not text:
        return (None, None)
    if _RX_NONE.search(text):
        return (0, 0)
    m = _RX_RANGE.search(text)
    if m:
        return (int(m.group(1)), int(m.group(2)))
    m = _RX_AT_LEAST.search(text)
    if m:
        return (int(m.group(1)), None)
    m = _RX_PLUS.search(text)
    if m:
        return (int(m.group(1)), None)
    m = _RX_NUM.search(text)
    if m:
        n = int(m.group(1))
        return (n, n)
    return (None, None)

# ---------- DOM extraction ----------

JOB_DETAILS_PANEL = (By.CSS_SELECTOR, "div.jobs-details__main-content, div.jobs-search__job-details--container")
JOB_TITLE  = (By.CSS_SELECTOR, "h1.t-24, h1.job-details-jobs-unified-top-card__job-title")
JOB_COMPANY = (By.CSS_SELECTOR, ".job-details-jobs-unified-top-card__company-name a, "
                                ".job-details-jobs-unified-top-card__company-name")
JOB_LOCATION = (By.CSS_SELECTOR, ".job-details-jobs-unified-top-card__primary-description-container span:first-child")
JOB_WORKSTYLE = (By.CSS_SELECTOR, ".job-details-jobs-unified-top-card__workplace-type")
JOB_POSTED   = (By.CSS_SELECTOR, "span.tvm__text--low-emphasis")
JOB_DESCRIPTION = (By.CSS_SELECTOR, "div.jobs-description__container, "
                                   "article.jobs-description__container, "
                                   "div.jobs-box__html-content")
JOB_CARD_ANCHOR = (By.CSS_SELECTOR, "a.job-card-container__link")

def wait_for_details_panel(driver: WebDriver, timeout: int = 15) -> bool:
    return wait_for(driver, *JOB_DETAILS_PANEL, timeout=timeout) is not None

def extract_job_details(driver: WebDriver, job_id: str, jd_url: str) -> dict:
    """Pull title/company/location/work_style/posted/JD/experience from the active panel."""
    if not wait_for_details_panel(driver):
        log.warning("details_panel_missing", extra={"job_id": job_id})
        return {"job_id": job_id, "jd_url": jd_url, "jd_full_text": ""}
    try:
        more = driver.find_element(By.CSS_SELECTOR, "button.jobs-description__footer-button")
        more.click()
        time.sleep(0.5)
    except Exception:
        pass

    title       = text_or_empty(driver, *JOB_TITLE)
    company     = text_or_empty(driver, *JOB_COMPANY)
    location    = text_or_empty(driver, *JOB_LOCATION)
    work_style  = text_or_empty(driver, *JOB_WORKSTYLE)
    posted      = text_or_empty(driver, *JOB_POSTED)
    jd_text     = text_or_empty(driver, *JOB_DESCRIPTION)

    exp_min, exp_max = extract_years(jd_text)

    return {
        "job_id": job_id,
        "title": title or None,
        "company": company or None,
        "location": location or None,
        "work_style": work_style or None,
        "posted_relative": posted or None,
        "experience_text": None,
        "experience_min": exp_min,
        "experience_max": exp_max,
        "salary_min_lpa": None,
        "salary_max_lpa": None,
        "salary_text": None,
        "jd_full_text": jd_text,
        "jd_url": jd_url,
    }
