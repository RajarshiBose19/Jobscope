from __future__ import annotations
import undetected_chromedriver as uc
from jobscope import config
from jobscope.utils.logging import get_logger

log = get_logger("scraper.browser")

def new_driver() -> uc.Chrome:
    opts = uc.ChromeOptions()
    if config.RUN_IN_BACKGROUND:
        opts.add_argument("--headless=new")
    if config.DISABLE_EXTENSIONS:
        opts.add_argument("--disable-extensions")
    opts.add_argument("--start-maximized")
    opts.add_argument("--disable-notifications")
    opts.page_load_strategy = "eager"
    config.CHROME_PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    opts.add_argument(f"--user-data-dir={config.CHROME_PROFILE_DIR}")
    log.info("launching_chrome", extra={"stealth": config.STEALTH_MODE,
                                        "headless": config.RUN_IN_BACKGROUND})
    driver = uc.Chrome(
        options=opts,
        use_subprocess=True,
        version_main=config.CHROME_VERSION_MAIN,
    )
    driver.set_page_load_timeout(60)
    return driver

def quit_driver(driver) -> None:
    try:
        driver.quit()
    except Exception:
        pass
