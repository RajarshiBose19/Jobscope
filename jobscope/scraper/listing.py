"""Iterate job cards in the search-results pane, click each, yield (job_id, url)."""
from __future__ import annotations
import time
from typing import Iterator, Tuple
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from jobscope import config
from jobscope.scraper._clickers import wait_for, safe_click
from jobscope.utils.logging import get_logger

log = get_logger("scraper.listing")

RESULTS_LIST = (By.CSS_SELECTOR, "ul.jobs-search__results-list, div.scaffold-layout__list ul")
JOB_CARD = (By.CSS_SELECTOR, "li[data-occludable-job-id], div.job-card-container")
NEXT_PAGE_BTN = (By.CSS_SELECTOR, "button[aria-label='View next page']")

def _scroll_into_view(driver: WebDriver, el) -> None:
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
    time.sleep(0.4)

def iter_listings(driver: WebDriver, max_pages: int = 10) -> Iterator[Tuple[str, str, int, int]]:
    """Yield (job_id, jd_url, page, position_on_page) for each card."""
    page = 1
    while page <= max_pages:
        results = wait_for(driver, *RESULTS_LIST, timeout=15)
        if not results:
            log.warning("results_list_missing")
            return
        cards = driver.find_elements(*JOB_CARD)
        if not cards:
            log.info("no_cards_on_page", extra={"page": page})
            return
        for idx, card in enumerate(cards, start=1):
            try:
                job_id = card.get_attribute("data-occludable-job-id") \
                         or card.get_attribute("data-job-id") \
                         or ""
                if not job_id:
                    anchor = card.find_element(By.CSS_SELECTOR, "a")
                    href = anchor.get_attribute("href") or ""
                    parts = [p for p in href.split("/") if p.isdigit()]
                    job_id = parts[0] if parts else ""
                jd_url = f"https://www.linkedin.com/jobs/view/{job_id}/" if job_id else ""
                _scroll_into_view(driver, card)
                if not safe_click(driver, card):
                    log.warning("card_click_failed", extra={"job_id": job_id})
                    continue
                time.sleep(config.CLICK_GAP_SEC)
                if job_id:
                    yield (job_id, jd_url, page, idx)
            except Exception as e:
                log.warning("listing_iter_error", extra={"err": str(e), "page": page, "idx": idx})
                continue
        try:
            nxt = driver.find_element(*NEXT_PAGE_BTN)
            if nxt.is_enabled():
                safe_click(driver, nxt)
                time.sleep(3)
                page += 1
                continue
        except Exception:
            pass
        return
