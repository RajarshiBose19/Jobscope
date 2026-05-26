"""Check whether the currently selected job shows the 'Applied' badge."""
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver

APPLIED_SELECTORS = [
    "span.jobs-s-apply__application-aware-text",
    ".artdeco-inline-feedback--success",
    "button.jobs-apply-button[aria-label*='Applied']",
]

def is_applied(driver: WebDriver) -> bool:
    for sel in APPLIED_SELECTORS:
        try:
            els = driver.find_elements(By.CSS_SELECTOR, sel)
            for el in els:
                txt = (el.text or el.get_attribute("aria-label") or "").lower()
                if "applied" in txt:
                    return True
        except Exception:
            continue
    return False
