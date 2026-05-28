from __future__ import annotations
import time
from typing import Literal, Optional
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from jobscope.scraper.applied_detector import is_applied
from jobscope.utils.logging import get_logger

log = get_logger("scraper.apply")

EASY_APPLY_MODAL_CSS = (
    "div.jobs-easy-apply-modal, "
    "div[aria-labelledby='jobs-apply-header'], "
    "div[role='dialog'][aria-labelledby*='apply']"
)


def _visible_buttons(driver: WebDriver) -> list[WebElement]:
    out: list[WebElement] = []
    try:
        for el in driver.find_elements(By.TAG_NAME, "button"):
            try:
                if el.is_displayed() and el.is_enabled():
                    out.append(el)
            except Exception:
                continue
    except Exception:
        pass
    return out


def _btn_text(btn: WebElement) -> tuple[str, str]:
    try:
        txt = (btn.text or "").strip().lower()
    except Exception:
        txt = ""
    try:
        aria = (btn.get_attribute("aria-label") or "").strip().lower()
    except Exception:
        aria = ""
    return txt, aria


def _scroll_into_view(driver: WebDriver, el: WebElement) -> None:
    try:
        driver.execute_script(
            "arguments[0].scrollIntoView({block:'center', inline:'center'});", el
        )
        time.sleep(0.2)
    except Exception:
        pass


def _click(driver: WebDriver, el: WebElement) -> bool:
    _scroll_into_view(driver, el)
    try:
        el.click()
        return True
    except Exception as e:
        log.info("native_click_failed_fallback_js", extra={"err": str(e)})
    try:
        driver.execute_script("arguments[0].click();", el)
        return True
    except Exception as e:
        log.warning("js_click_failed", extra={"err": str(e)})
        return False


def find_apply_button(driver: WebDriver) -> Optional[WebElement]:
    candidates = []
    for btn in _visible_buttons(driver):
        txt, aria = _btn_text(btn)
        if "save" in aria and "easy" not in aria:
            continue
        if txt in ("save", "saved", "unsave"):
            continue
        if txt in ("apply", "easy apply", "apply now") \
           or aria.startswith("apply ") or aria.startswith("easy apply") \
           or "apply to " in aria:
            candidates.append((btn, txt, aria))
    if not candidates:
        log.warning("apply_button_not_found",
                    extra={"button_count": len(_visible_buttons(driver))})
        return None
    candidates.sort(key=lambda c: (
        0 if c[2].startswith("easy apply") else
        1 if c[2].startswith("apply to") else
        2 if c[1] == "easy apply" else
        3 if c[1] == "apply" else 4
    ))
    btn, txt, aria = candidates[0]
    log.info("apply_button_found", extra={"text": txt, "aria": aria})
    return btn


def is_easy_apply(driver: WebDriver) -> bool:
    btn = find_apply_button(driver)
    if not btn:
        return False
    txt, aria = _btn_text(btn)
    return "easy apply" in aria or "easy apply" in txt


def click_apply_button(driver: WebDriver) -> bool:
    btn = find_apply_button(driver)
    if not btn:
        return False
    ok = _click(driver, btn)
    if ok:
        log.info("apply_button_clicked")
    else:
        log.warning("apply_button_click_failed")
    return ok


def _click_done_button(driver: WebDriver) -> bool:
    candidates = []
    try:
        for btn in driver.find_elements(By.CSS_SELECTOR,
            "button, button[aria-label*='Done' i], "
            "button[aria-label*='Dismiss' i], button[aria-label*='Close' i]"
        ):
            try:
                if not btn.is_displayed() or not btn.is_enabled():
                    continue
                text = (btn.text or "").strip().lower()
                aria = (btn.get_attribute("aria-label") or "").strip().lower()
                if text in ("done", "close", "dismiss") \
                   or aria in ("done", "close", "dismiss") \
                   or aria.startswith("dismiss"):
                    candidates.append((btn, text or aria))
            except Exception:
                continue
    except Exception:
        pass
    for btn, label in candidates:
        try:
            if _click(driver, btn):
                log.info("done_button_clicked", extra={"label": label})
                return True
        except Exception:
            continue
    log.warning("done_button_not_found")
    return False


def _success_modal_visible(driver: WebDriver) -> bool:
    needles = ("application was sent", "your application has been sent",
               "application sent", "your application is on its way",
               "application submitted")
    try:
        for sel in ("h2", "h3", "div[role='dialog']", "div.jobs-easy-apply-modal__header"):
            for el in driver.find_elements(By.CSS_SELECTOR, sel):
                try:
                    if not el.is_displayed():
                        continue
                    t = (el.text or "").strip().lower()
                    if any(n in t for n in needles):
                        return True
                except Exception:
                    continue
    except Exception:
        pass
    return False


def wait_easy_apply_resolution(
    driver: WebDriver, *, timeout_sec: int = 300, poll_sec: float = 1.0,
) -> Literal["submitted", "abandoned", "timeout"]:
    deadline = time.monotonic() + timeout_sec
    saw_modal = False
    saw_success_in_modal = False
    grace_deadline = time.monotonic() + 5
    while time.monotonic() < grace_deadline:
        modal_elems = driver.find_elements(By.CSS_SELECTOR, EASY_APPLY_MODAL_CSS)
        if any(el.is_displayed() for el in modal_elems):
            saw_modal = True
            log.info("easy_apply_modal_visible")
            break
        time.sleep(0.3)
    if not saw_modal:
        log.info("easy_apply_no_modal_seen")
    timed_out = False
    done_clicked = False
    while saw_modal:
        if time.monotonic() >= deadline:
            timed_out = True
            break
        if _success_modal_visible(driver):
            saw_success_in_modal = True
            if not done_clicked:
                log.info("easy_apply_success_header_seen")
                if _click_done_button(driver):
                    done_clicked = True
                    time.sleep(0.5)
        modal_elems = driver.find_elements(By.CSS_SELECTOR, EASY_APPLY_MODAL_CSS)
        if not any(el.is_displayed() for el in modal_elems):
            log.info("easy_apply_modal_closed")
            break
        time.sleep(0.3 if saw_success_in_modal else poll_sec)
    if timed_out:
        log.warning("easy_apply_modal_timeout")
        return "timeout"
    if saw_success_in_modal:
        return "submitted"

    for i in range(12):
        if is_applied(driver):
            log.info("applied_detected_post_modal", extra={"after_polls": i + 1})
            return "submitted"
        time.sleep(0.5)
    log.warning("applied_not_detected_after_modal_close")
    return "abandoned"


SAVE_STATE_SAVE = "save"
SAVE_STATE_SAVED = "saved"
SAVE_STATE_NONE = "none"


def _classify_save_text(txt: str, aria: str) -> str:
    t = (txt or "").strip().lower()
    a = (aria or "").strip().lower()
    if t in ("saved", "unsave") or a.startswith("saved") \
       or a.startswith("unsave") or "click to unsave" in a \
       or "click to remove from saved" in a:
        return SAVE_STATE_SAVED
    if t in ("save", "save job"):
        return SAVE_STATE_SAVE
    if a == "save" or a.startswith("save ") or "click to save" in a:
        return SAVE_STATE_SAVE
    return SAVE_STATE_NONE


def find_save_button(driver: WebDriver) -> tuple[Optional[WebElement], str]:
    try:
        legacy = driver.find_elements(By.CSS_SELECTOR, "button.jobs-save-button")
        for btn in legacy:
            if not btn.is_displayed() or not btn.is_enabled():
                continue
            txt, aria = _btn_text(btn)
            state = _classify_save_text(txt, aria)
            if state in (SAVE_STATE_SAVE, SAVE_STATE_SAVED):
                log.info("save_button_found_legacy",
                         extra={"state": state, "text": txt, "aria": aria})
                return btn, state
            log.info("save_button_found_legacy_untexted",
                     extra={"text": txt, "aria": aria})
            return btn, SAVE_STATE_SAVE
    except Exception:
        pass

    candidates: list[tuple[WebElement, str, str, str]] = []
    for btn in _visible_buttons(driver):
        txt, aria = _btn_text(btn)
        if "easy apply" in aria or "easy apply" in txt:
            continue
        if aria.startswith("apply ") or aria.startswith("apply to") \
           or txt in ("apply", "apply now"):
            continue
        state = _classify_save_text(txt, aria)
        if state != SAVE_STATE_NONE:
            candidates.append((btn, state, txt, aria))
    for btn, state, txt, aria in candidates:
        if state == SAVE_STATE_SAVED:
            log.info("save_button_already_saved",
                     extra={"aria": aria, "text": txt})
            return btn, SAVE_STATE_SAVED
    for btn, state, txt, aria in candidates:
        if state == SAVE_STATE_SAVE:
            log.info("save_button_found_byscan",
                     extra={"aria": aria, "text": txt})
            return btn, SAVE_STATE_SAVE

    try:
        anchors = driver.find_elements(
            By.CSS_SELECTOR, "[role='button']:not(button)"
        )
        for el in anchors:
            if not el.is_displayed():
                continue
            txt = (el.text or "").strip().lower()
            aria = (el.get_attribute("aria-label") or "").strip().lower()
            state = _classify_save_text(txt, aria)
            if state == SAVE_STATE_SAVED:
                log.info("save_button_already_saved_roleattr",
                         extra={"aria": aria, "text": txt})
                return el, SAVE_STATE_SAVED
            if state == SAVE_STATE_SAVE:
                log.info("save_button_found_roleattr",
                         extra={"aria": aria, "text": txt})
                return el, SAVE_STATE_SAVE
    except Exception:
        pass

    log.warning("save_button_not_found",
                extra={"button_count": len(_visible_buttons(driver))})
    return None, SAVE_STATE_NONE


def click_save_button(driver: WebDriver) -> bool:
    btn, state = find_save_button(driver)
    if state == SAVE_STATE_SAVED:
        return True
    if state == SAVE_STATE_SAVE and btn is not None:
        ok = _click(driver, btn)
        if ok:
            time.sleep(0.8)
            _, new_state = find_save_button(driver)
            log.info("save_button_clicked",
                     extra={"new_state": new_state})
            return True
        log.warning("save_button_click_failed")
        return False
    return False
