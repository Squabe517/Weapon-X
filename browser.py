"""Shared Chrome driver setup and session handling for the Target scripts."""

import logging
import os
import time
from pathlib import Path

from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

logger = logging.getLogger(__name__)

ACCOUNT_URL = "https://www.target.com/account"
ACCOUNT_LINK = (By.CSS_SELECTOR, "a[data-test*='account']")
DEFAULT_PROFILE_DIR = Path(__file__).resolve().parent / "chrome-profile"


def create_driver() -> webdriver.Chrome:
    """Create Chrome using a dedicated persistent profile so logins are kept.

    The profile must not be Chrome's default one (Chrome 136+ disables
    automation on it) and must not be open in another Chrome instance.
    """
    profile = Path(os.environ.get("CHROME_PROFILE_DIR", DEFAULT_PROFILE_DIR))
    profile.mkdir(parents=True, exist_ok=True)
    logger.info(f"Starting Chrome with profile {profile}")

    options = webdriver.ChromeOptions()
    options.page_load_strategy = "eager"
    options.add_argument(f"--user-data-dir={profile}")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--window-size=1366,768")

    # Selenium Manager resolves the driver automatically
    driver = webdriver.Chrome(options=options)
    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"},
    )
    return driver


CHALLENGE = (
    By.XPATH,
    "//*[contains(normalize-space(.), 'Press & hold') or contains(normalize-space(.), 'Quick verification')][not(*)]"
    " | //*[@id='px-captcha']",
)


def challenge_present(driver) -> bool:
    return bool(driver.find_elements(*CHALLENGE))


def wait_for_human_verification(driver, timeout: int = 300) -> bool:
    """If Target shows a human-verification challenge, wait for the user to solve it."""
    if not challenge_present(driver):
        return True
    logger.warning(
        "Human verification (press & hold) detected. Please solve it in the browser "
        f"window. Waiting up to {timeout}s..."
    )
    print("\a", end="")
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        time.sleep(2)
        if not challenge_present(driver):
            logger.info("Verification cleared.")
            return True
    logger.error("Timed out waiting for human verification.")
    return False


def get_page(driver, url: str) -> bool:
    """Navigate to url, pausing for manual verification if it is requested."""
    driver.get(url)
    return wait_for_human_verification(driver)


def is_logged_in(driver, wait_seconds: float = 8) -> bool:
    """Return True if the saved session is logged in to Target."""
    if not get_page(driver, ACCOUNT_URL):
        return False
    try:
        WebDriverWait(driver, wait_seconds).until(EC.presence_of_element_located(ACCOUNT_LINK))
        return True
    except TimeoutException:
        return False


def account_name(driver) -> str | None:
    try:
        return driver.find_element(By.CSS_SELECTOR, "span[data-test*='accountName']").text
    except NoSuchElementException:
        return None


def ensure_logged_in(driver, timeout: int = 300) -> bool:
    """Return True once logged in, waiting for a manual login if needed."""
    if is_logged_in(driver):
        logger.info("Existing Target session is valid.")
        return True

    logger.warning(
        "Not logged in. Please log in to Target in the browser window "
        f"(security key or emailed code). Waiting up to {timeout}s..."
    )
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            WebDriverWait(driver, 5).until(EC.presence_of_element_located(ACCOUNT_LINK))
            logger.info("Login detected.")
            return True
        except TimeoutException:
            continue
    logger.error("Timed out waiting for manual login.")
    return False
