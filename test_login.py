"""
Check that the saved Target session (persistent Chrome profile) is logged in.

First run: a Chrome window opens; log in to Target manually (security key or
emailed code). The session is saved in the chrome-profile directory and reused
by this script and by pokemon_restock.py.

Usage: python test_login.py
"""

import logging
import sys

from browser import account_name, create_driver, ensure_logged_in

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def main() -> int:
    driver = create_driver()
    try:
        if not ensure_logged_in(driver):
            logger.error("LOGIN FAILED - no logged-in session detected.")
            return 1
        logger.info("LOGIN SUCCESSFUL! Session saved in the Chrome profile.")
        name = account_name(driver)
        if name:
            logger.info(f"Logged in as: {name}")
        input("Press Enter to close the browser...")
        return 0
    except Exception:
        logger.exception("An error occurred")
        return 1
    finally:
        driver.quit()


if __name__ == "__main__":
    sys.exit(main())
