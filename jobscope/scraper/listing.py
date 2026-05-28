from __future__ import annotations
import time
from typing import Iterator, Optional, TypedDict
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from jobscope import config
from jobscope.scraper._clickers import wait_for, safe_click
from jobscope.utils.logging import get_logger

log = get_logger("scraper.listing")

RESULTS_LIST = (By.CSS_SELECTOR, "ul.jobs-search__results-list, div.scaffold-layout__list ul")
JOB_CARD = (By.CSS_SELECTOR, "li[data-occludable-job-id], div.job-card-container")
NEXT_PAGE_BTN = (By.CSS_SELECTOR, "button[aria-label='View next page']")
NEXT_PAGE_BTN_BY_NUM_XPATH = "//button[@aria-label='Page {n}']"

COMPANY_SUBTITLE_CLASS = "artdeco-entity-lockup__subtitle"
APPLIED_BADGE_CLASS = "job-card-container__footer-job-state"


class CardYield(TypedDict):
    job_id: str
    jd_url: str
    page: int
    position_on_page: int
    company_hint: str
    already_applied: bool
    clicked: bool


def _scroll_into_view(driver: WebDriver, el: WebElement) -> None:
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
    time.sleep(0.3)


def _peek_card(card: WebElement) -> tuple[str, str, bool]:
    job_id = (card.get_attribute("data-occludable-job-id")
              or card.get_attribute("data-job-id") or "")
    if not job_id:
        try:
            anchor = card.find_element(By.CSS_SELECTOR, "a")
            href = anchor.get_attribute("href") or ""
            parts = [p for p in href.split("/") if p.isdigit()]
            job_id = parts[0] if parts else ""
        except Exception:
            pass

    company_hint = ""
    try:
        sub = card.find_element(By.CLASS_NAME, COMPANY_SUBTITLE_CLASS)
        raw = (sub.text or "").strip()
        company_hint = raw.split(" · ", 1)[0].strip() if " · " in raw else raw
    except Exception:
        pass

    already_applied = False
    try:
        badge = card.find_element(By.CLASS_NAME, APPLIED_BADGE_CLASS)
        already_applied = "applied" in (badge.text or "").lower()
    except Exception:
        pass

    return job_id, company_hint, already_applied


def _is_blacklisted(company_hint: str) -> bool:
    if not company_hint:
        return False
    blacklist = {c.strip().lower() for c in config.BLACKLISTED_COMPANIES}
    return company_hint.strip().lower() in blacklist


def iter_listings(driver: WebDriver, max_pages: int = 10) -> Iterator[CardYield]:
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
        seen_on_page: set[str] = set()
        idx = 0
        for card in cards:
            try:
                job_id, company_hint, already_applied = _peek_card(card)
                if not job_id or job_id in seen_on_page:
                    continue
                seen_on_page.add(job_id)
                idx += 1
                jd_url = f"https://www.linkedin.com/jobs/view/{job_id}/"

                if already_applied:
                    log.info("pre_skip_already_applied",
                             extra={"job_id": job_id, "company": company_hint})
                    yield CardYield(
                        job_id=job_id, jd_url=jd_url, page=page,
                        position_on_page=idx, company_hint=company_hint,
                        already_applied=True, clicked=False,
                    )
                    continue
                if _is_blacklisted(company_hint):
                    log.info("pre_skip_blacklisted_company",
                             extra={"job_id": job_id, "company": company_hint})
                    yield CardYield(
                        job_id=job_id, jd_url=jd_url, page=page,
                        position_on_page=idx, company_hint=company_hint,
                        already_applied=False, clicked=False,
                    )
                    continue

                _scroll_into_view(driver, card)
                if not safe_click(driver, card):
                    log.warning("card_click_failed", extra={"job_id": job_id})
                    continue
                time.sleep(config.CLICK_GAP_SEC)
                yield CardYield(
                    job_id=job_id, jd_url=jd_url, page=page,
                    position_on_page=idx, company_hint=company_hint,
                    already_applied=False, clicked=True,
                )
            except Exception as e:
                log.warning("listing_iter_error",
                            extra={"err": str(e), "page": page})
                continue
        advanced = False
        try:
            nxt = driver.find_element(*NEXT_PAGE_BTN)
            if nxt.is_enabled() and nxt.is_displayed():
                _scroll_into_view(driver, nxt)
                if safe_click(driver, nxt):
                    log.info("paginated_via_next_arrow", extra={"to_page": page + 1})
                    advanced = True
        except Exception:
            pass
        if not advanced:
            try:
                next_num_btn = driver.find_element(
                    By.XPATH, NEXT_PAGE_BTN_BY_NUM_XPATH.format(n=page + 1)
                )
                if next_num_btn.is_enabled() and next_num_btn.is_displayed():
                    _scroll_into_view(driver, next_num_btn)
                    if safe_click(driver, next_num_btn):
                        log.info("paginated_via_page_num", extra={"to_page": page + 1})
                        advanced = True
            except Exception:
                pass
        if advanced:
            time.sleep(3)
            page += 1
            continue
        log.info("pagination_end", extra={"last_page": page})
        return
