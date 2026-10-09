"""
Target Pokémon Card Stock Monitor and Automatic Purchaser

Monitors the stock status of specific Pokémon card items on Target's website.
When an item comes back in stock, it logs into your Target account, adds the
item to the cart, and proceeds through checkout.

Usage:
1. Set your Target credentials in a .env file (see .env.template).
2. Run: python pokemon_restock.py

Note: Be respectful of Target's servers by using reasonable delays between checks.
"""

import logging
import os
import random
import time

from dotenv import load_dotenv
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from browser import create_driver, ensure_logged_in, get_page, is_logged_in

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("pokemon_restock.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

load_dotenv()

TARGET_ITEMS = [
    {
        "url": "https://www.target.com/p/pok-233-mon-trading-card-game-scarlet-38-violet-151-binder-collection/-/A-89444929",
        "name": "Pokémon Scarlet & Violet 151 Binder Collection",
    },
]

CHECK_INTERVAL = int(os.environ.get("CHECK_INTERVAL", 60))
MAX_RETRIES = int(os.environ.get("MAX_RETRIES", 3))
SESSION_RECHECK_SECONDS = 30 * 60

ADD_TO_CART = (By.XPATH, "//button[contains(normalize-space(.), 'Add to cart')]")
OUT_OF_STOCK = (
    By.XPATH,
    "//*[contains(normalize-space(.), 'Out of stock') or contains(normalize-space(.), 'Sold out')"
    " or contains(normalize-space(.), 'Currently unavailable')][not(*)]",
)


class TargetPokemonRestockMonitor:
    def __init__(self):
        self.driver = create_driver()
        self.wait = WebDriverWait(self.driver, 10)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def check_stock(self, item):
        """Return True if the item appears to be in stock."""
        try:
            logger.info(f"Checking stock for {item['name']}...")
            get_page(self.driver, item["url"])
            self.wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            time.sleep(random.uniform(1, 3))

            if self.driver.find_elements(*OUT_OF_STOCK):
                logger.info(f"{item['name']} is out of stock.")
                return False

            WebDriverWait(self.driver, 5).until(EC.presence_of_element_located(ADD_TO_CART))
            logger.info(f"ITEM IS IN STOCK! {item['name']} is available for purchase!")
            return True
        except TimeoutException:
            logger.info(f"Could not determine stock status for {item['name']} (timeout).")
            return False
        except WebDriverException as e:
            logger.error(f"Error checking stock for {item['name']}: {e}")
            return False

    def login(self):
        """Ensure the persistent Chrome profile has a logged-in Target session."""
        return ensure_logged_in(self.driver)

    def add_to_cart(self, item):
        """Add the item to the cart. Return True on success."""
        try:
            logger.info(f"Attempting to add {item['name']} to cart...")
            if item["url"] not in self.driver.current_url:
                get_page(self.driver, item["url"])

            self.wait.until(EC.element_to_be_clickable(ADD_TO_CART)).click()

            self.wait.until(
                EC.presence_of_element_located(
                    (
                        By.XPATH,
                        "//*[contains(., 'Added to cart') or contains(., 'Item added to cart')][not(*)]",
                    )
                )
            )
            logger.info(f"Successfully added {item['name']} to cart.")
            return True
        except TimeoutException:
            logger.error(f"Failed to add {item['name']} to cart - no confirmation found.")
            return False
        except WebDriverException as e:
            logger.error(f"Error adding {item['name']} to cart: {e}")
            return False

    def checkout(self):
        """Proceed through checkout up to the final confirmation."""
        try:
            logger.info("Proceeding to checkout...")
            get_page(self.driver, "https://www.target.com/co-cart")

            self.wait.until(
                EC.element_to_be_clickable(
                    (By.XPATH, "//button[contains(normalize-space(.), 'Check out')]")
                )
            ).click()

            place_order = WebDriverWait(self.driver, 15).until(
                EC.element_to_be_clickable(
                    (By.XPATH, "//button[contains(normalize-space(.), 'Place your order')"
                               " or contains(normalize-space(.), 'Place order')]")
                )
            )

            # Uncomment once you're sure everything works correctly
            # place_order.click()

            logger.info("Checkout ready. The final 'Place order' click is disabled for safety.")
            logger.info("Review your order in the browser and place it manually.")
            input("Press Enter to close the browser...")
            return True
        except TimeoutException:
            logger.error("Checkout timed out.")
            return False
        except WebDriverException as e:
            logger.error(f"Error during checkout: {e}")
            return False

    def purchase_when_in_stock(self):
        """Poll the configured items; buy the first one that comes into stock."""
        if not self.login():
            logger.error("Login failed; aborting.")
            return False

        last_session_check = time.monotonic()

        while True:
            if time.monotonic() - last_session_check > SESSION_RECHECK_SECONDS:
                if not is_logged_in(self.driver):
                    logger.error("Session expired. Run test_login.py (or re-login in the window) and restart.")
                    if not ensure_logged_in(self.driver):
                        return False
                last_session_check = time.monotonic()

            for item in TARGET_ITEMS:
                if not self.check_stock(item):
                    continue
                for attempt in range(1, MAX_RETRIES + 1):
                    logger.info(f"Purchase attempt {attempt}/{MAX_RETRIES} for {item['name']}")
                    if self.add_to_cart(item) and self.checkout():
                        return True
                logger.error(f"All purchase attempts failed for {item['name']}.")

            delay = CHECK_INTERVAL + random.uniform(-0.2, 0.2) * CHECK_INTERVAL
            logger.info(f"Sleeping {delay:.0f}s before next check...")
            time.sleep(delay)

    def close(self):
        self.driver.quit()


if __name__ == "__main__":
    try:
        with TargetPokemonRestockMonitor() as monitor:
            monitor.purchase_when_in_stock()
    except KeyboardInterrupt:
        logger.info("Stopped by user.")
    except Exception:
        logger.exception("Fatal error")
