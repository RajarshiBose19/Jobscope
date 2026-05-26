"""LinkedIn login with 2FA/captcha pause support."""
from __future__ import annotations
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from jobscope import config
from jobscope.scraper._clickers import wait_for, wait_clickable, safe_click
from jobscope.utils.logging import get_logger

log = get_logger("scraper.login")

class LoginFailure(Exception):
    pass

LOGIN_URL = "https://www.linkedin.com/login"
HOME_URL = "https://www.linkedin.com/feed/"

def is_logged_in(driver: WebDriver) -> bool:
    driver.get(HOME_URL)
    time.sleep(2)
    return "feed" in driver.current_url and "/login" not in driver.current_url

def login(driver: WebDriver, *, on_verification=None) -> None:
    """Log in. If LinkedIn shows captcha/2FA, calls on_verification (a blocking callable)."""
    if is_logged_in(driver):
        log.info("already_logged_in")
        return
    driver.get(LOGIN_URL)
    user_field = wait_for(driver, By.ID, "username", timeout=15)
    pass_field = wait_for(driver, By.ID, "password", timeout=5)
    if not user_field or not pass_field:
        raise LoginFailure("login page didn't load")
    user_field.clear(); user_field.send_keys(config.LINKEDIN_USERNAME)
    pass_field.clear(); pass_field.send_keys(config.LINKEDIN_PASSWORD)
    submit = wait_clickable(driver, By.CSS_SELECTOR, "button[type='submit']", 5)
    if not submit or not safe_click(driver, submit):
        raise LoginFailure("could not click submit")
    time.sleep(4)
    for _ in range(60):
        url = driver.current_url
        if "feed" in url and "/login" not in url:
            log.info("login_success")
            return
        if any(x in url for x in ("checkpoint", "challenge", "captcha", "uas/login-submit")):
            log.warning("login_verification_required", extra={"url": url})
            if on_verification:
                on_verification()
            time.sleep(5)
            continue
        time.sleep(5)
    raise LoginFailure(f"login did not complete; last url: {driver.current_url}")
