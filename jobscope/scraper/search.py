from __future__ import annotations
import time
from urllib.parse import urlencode, quote
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from jobscope import config
from jobscope.scraper._clickers import wait_for, wait_clickable, safe_click
from jobscope.utils.logging import get_logger

log = get_logger("scraper.search")

SEARCH_BASE = "https://www.linkedin.com/jobs/search/"

_F_EXP = {"Internship":"1","Entry level":"2","Associate":"3",
          "Mid-Senior level":"4","Director":"5","Executive":"6"}
_F_JOB = {"Full-time":"F","Part-time":"P","Contract":"C","Temporary":"T",
          "Internship":"I","Volunteer":"V","Other":"O"}
_F_WP  = {"On-site":"1","Remote":"2","Hybrid":"3"}
_F_DATE = {"Past 24 hours":"r86400","Past week":"r604800","Past month":"r2592000","Any time":""}

def build_search_url(term: str) -> str:
    params = {
        "keywords": term,
        "location": config.SEARCH_LOCATION,
        "f_E": ",".join(_F_EXP[e] for e in config.EXPERIENCE_LEVELS if e in _F_EXP),
        "f_JT": ",".join(_F_JOB[j] for j in config.JOB_TYPES if j in _F_JOB),
        "f_WT": ",".join(_F_WP[w] for w in config.ON_SITE if w in _F_WP),
        "f_TPR": _F_DATE.get(config.DATE_POSTED, ""),
    }
    if config.EASY_APPLY_ONLY:
        params["f_AL"] = "true"
    params = {k: v for k, v in params.items() if v}
    return SEARCH_BASE + "?" + urlencode(params, quote_via=quote)

def navigate_to_search(driver: WebDriver, term: str) -> None:
    url = build_search_url(term)
    log.info("navigate_search", extra={"term": term, "url": url})
    try:
        driver.get(url)
    except TimeoutException:
        log.warning("navigate_search_page_timeout", extra={"term": term})
        try:
            driver.execute_script("window.stop();")
        except Exception:
            pass
    time.sleep(3)
    wait_for(driver, By.CSS_SELECTOR,
             "ul.jobs-search__results-list, div.jobs-search-results-list", timeout=30)
