from __future__ import annotations
import time
from typing import Optional
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException, ElementClickInterceptedException,
    StaleElementReferenceException, NoSuchElementException,
)

def wait_for(driver: WebDriver, by, selector: str, timeout: int = 10) -> Optional[WebElement]:
    try:
        return WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((by, selector))
        )
    except TimeoutException:
        return None

def wait_clickable(driver: WebDriver, by, selector: str, timeout: int = 10) -> Optional[WebElement]:
    try:
        return WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable((by, selector))
        )
    except TimeoutException:
        return None

def safe_click(driver: WebDriver, element: WebElement, retries: int = 3) -> bool:
    for _ in range(retries):
        try:
            element.click()
            return True
        except (ElementClickInterceptedException, StaleElementReferenceException):
            time.sleep(0.5)
        except Exception:
            try:
                driver.execute_script("arguments[0].click();", element)
                return True
            except Exception:
                time.sleep(0.5)
    return False

def find_or_none(parent, by, selector: str) -> Optional[WebElement]:
    try:
        return parent.find_element(by, selector)
    except NoSuchElementException:
        return None

def text_or_empty(parent, by, selector: str) -> str:
    el = find_or_none(parent, by, selector)
    return (el.text or "").strip() if el else ""

def attr_or_empty(parent, by, selector: str, attr: str) -> str:
    el = find_or_none(parent, by, selector)
    return (el.get_attribute(attr) or "").strip() if el else ""
