from __future__ import annotations
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from jobscope.utils.logging import get_logger

log = get_logger("scraper.applied_detector")

APPLIED_SCAN_SELECTORS = [
    "div.jobs-details__main-content",
    "div.job-details-jobs-unified-top-card__container--two-pane",
    "div.jobs-s-apply",
    "div.artdeco-inline-feedback",
    "span.jobs-s-apply__application-aware-text",
    "button.jobs-apply-button",
]


def _text_says_applied(text: str) -> bool:
    if not text:
        return False
    t = text.strip().lower()
    if not t:
        return False
    if t.startswith("applied"):
        return True
    if t == "applied" or "you applied" in t or "already applied" in t:
        return True
    return False


def is_applied(driver: WebDriver) -> bool:
    try:
        for btn in driver.find_elements(By.CSS_SELECTOR,
            "button.jobs-apply-button, "
            "button[data-job-id], "
            "button[aria-label*='pplied' i]"
        ):
            try:
                if not btn.is_displayed():
                    continue
                aria = (btn.get_attribute("aria-label") or "").strip().lower()
                text = (btn.text or "").strip().lower()
                disabled = btn.get_attribute("disabled") is not None
                if _text_says_applied(aria) or _text_says_applied(text):
                    log.info("applied_detected_via_apply_btn",
                             extra={"text": text[:50], "aria": aria[:50],
                                    "disabled": disabled})
                    return True
            except Exception:
                continue
    except Exception:
        pass

    for sel in APPLIED_SCAN_SELECTORS:
        try:
            for el in driver.find_elements(By.CSS_SELECTOR, sel):
                try:
                    if not el.is_displayed():
                        continue
                    text = (el.text or "").strip()
                    aria = (el.get_attribute("aria-label") or "").strip()
                    if _text_says_applied(text) or _text_says_applied(aria):
                        log.info("applied_detected_via_scan",
                                 extra={"selector": sel,
                                        "snippet": (text or aria)[:80]})
                        return True
                except Exception:
                    continue
        except Exception:
            continue

    try:
        for el in driver.find_elements(By.CSS_SELECTOR,
            "span, div.t-bold, span.t-bold, div[class*='feedback']"
        )[:80]:
            try:
                if not el.is_displayed():
                    continue
                t = (el.text or "").strip()
                if _text_says_applied(t):
                    log.info("applied_detected_via_text_scan",
                             extra={"snippet": t[:80]})
                    return True
            except Exception:
                continue
    except Exception:
        pass

    return False
