from __future__ import annotations
import re
import time
from typing import Optional
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from jobscope.scraper._clickers import wait_for, text_or_empty, attr_or_empty
from jobscope.utils.logging import get_logger

log = get_logger("scraper.extract")

_RX_RANGE = re.compile(r"(\d{1,2})\s*(?:-|to|–|—)\s*(\d{1,2})\s*(?:\+)?\s*(?:years?|yrs?)", re.I)
_RX_PLUS  = re.compile(r"(\d{1,2})\s*\+\s*(?:years?|yrs?)", re.I)
_RX_AT_LEAST = re.compile(r"(?:at\s*least|minimum|min\.?)\s*(\d{1,2})\s*(?:years?|yrs?)", re.I)
_RX_NUM   = re.compile(r"\b(\d{1,2})\s*(?:years?|yrs?)\b", re.I)
_RX_NONE  = re.compile(r"(?:\bno\s+experience\b|\bfresher\b|\bfresh\s+grad\w*|\bentry[-\s]level\b)", re.I)

_RX_RUPEE_RANGE_LPA = re.compile(
    r"(?:₹|inr|rs\.?)\s*(\d+(?:\.\d+)?)\s*(?:lpa|l\b|lakhs?)?\s*(?:-|to|–|—)\s*(?:₹|inr|rs\.?)?\s*(\d+(?:\.\d+)?)\s*(?:lpa|l\b|lakhs?)",
    re.I,
)
_RX_PLAIN_RANGE_LPA = re.compile(
    r"(\d+(?:\.\d+)?)\s*(?:lpa|l\b|lakhs?)?\s*(?:-|to|–|—)\s*(\d+(?:\.\d+)?)\s*(?:lpa|l\b|lakhs?)\s*(?:p\.?a\.?|per\s*annum)?",
    re.I,
)
_RX_SINGLE_LPA = re.compile(
    r"(?:₹|inr|rs\.?)?\s*(\d+(?:\.\d+)?)\s*(?:lpa|lakhs?)\s*(?:p\.?a\.?|per\s*annum)?",
    re.I,
)
_RX_RUPEE_RANGE_FULL = re.compile(
    r"(?:₹|inr|rs\.?)\s*([\d,]{5,})\s*(?:-|to|–|—)\s*(?:₹|inr|rs\.?)?\s*([\d,]{5,})",
    re.I,
)


def _rupees_to_lpa(rupees_str: str) -> Optional[float]:
    try:
        n = float(rupees_str.replace(",", ""))
        if n < 1000:
            return None
        return round(n / 100000.0, 2)
    except Exception:
        return None


def extract_salary_lpa(text: str) -> tuple[Optional[float], Optional[float], Optional[str]]:
    if not text:
        return (None, None, None)
    m = _RX_RUPEE_RANGE_LPA.search(text)
    if m:
        return (float(m.group(1)), float(m.group(2)), m.group(0))
    m = _RX_PLAIN_RANGE_LPA.search(text)
    if m:
        a, b = float(m.group(1)), float(m.group(2))
        if 1 <= a <= 200 and 1 <= b <= 200:
            return (a, b, m.group(0))
    m = _RX_RUPEE_RANGE_FULL.search(text)
    if m:
        a = _rupees_to_lpa(m.group(1))
        b = _rupees_to_lpa(m.group(2))
        if a is not None and b is not None:
            return (a, b, m.group(0))
    m = _RX_SINGLE_LPA.search(text)
    if m:
        v = float(m.group(1))
        if 1 <= v <= 200:
            return (v, v, m.group(0))
    return (None, None, None)


def extract_years(text: str) -> tuple[Optional[int], Optional[int]]:
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
JOB_INSIGHTS = (By.CSS_SELECTOR,
    ".job-details-jobs-unified-top-card__job-insight, "
    ".job-details-jobs-unified-top-card__job-insight-text-description, "
    ".jobs-details-jobs-unified-top-card__job-insight, "
    ".job-details-preferences-and-skills__pill, "
    ".jobs-unified-top-card__job-insight")
JOB_CARD_ANCHOR = (By.CSS_SELECTOR, "a.job-card-container__link")


def _scrape_salary_text(driver: WebDriver) -> str:
    parts: list[str] = []
    try:
        for el in driver.find_elements(*JOB_INSIGHTS):
            try:
                t = (el.text or "").strip()
                if t:
                    parts.append(t)
            except Exception:
                continue
    except Exception:
        pass
    return " | ".join(parts)

def wait_for_details_panel(driver: WebDriver, timeout: int = 15) -> bool:
    return wait_for(driver, *JOB_DETAILS_PANEL, timeout=timeout) is not None

def extract_job_details(driver: WebDriver, job_id: str, jd_url: str) -> dict:
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

    insights_text = _scrape_salary_text(driver)
    sal_min, sal_max, sal_match = extract_salary_lpa(insights_text)
    if sal_min is None:
        sal_min, sal_max, sal_match = extract_salary_lpa(jd_text)
    if sal_match:
        log.info("salary_extracted",
                 extra={"job_id": job_id, "min": sal_min, "max": sal_max,
                        "match": sal_match[:60]})
    else:
        log.info("salary_not_found", extra={"job_id": job_id})

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
        "salary_min_lpa": sal_min,
        "salary_max_lpa": sal_max,
        "salary_text": sal_match,
        "jd_full_text": jd_text,
        "jd_url": jd_url,
    }
