"""Chrome bootstrap with undetected-chromedriver."""
from __future__ import annotations
import undetected_chromedriver as uc
from selenium.webdriver.chrome.options import Options
from jobscope import config
from jobscope.utils.logging import get_logger

log = get_logger("scraper.browser")

def new_driver() -> uc.Chrome:
    """Return a configured undetected-chromedriver Chrome."""
    opts = Options()
    if config.RUN_IN_BACKGROUND:
        opts.add_argument("--headless=new")
    if config.DISABLE_EXTENSIONS:
        opts.add_argument("--disable-extensions")
    opts.add_argument("--start-maximized")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument("--disable-notifications")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    log.info("launching_chrome", extra={"stealth": config.STEALTH_MODE,
                                        "headless": config.RUN_IN_BACKGROUND})
    driver = uc.Chrome(options=opts, use_subprocess=True)
    driver.set_page_load_timeout(45)
    return driver

def quit_driver(driver) -> None:
    try:
        driver.quit()
    except Exception:
        pass
