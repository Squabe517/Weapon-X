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
from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

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
EMAIL = os.environ.get("TARGET_EMAIL", "YOUR_EMAIL")
PASSWORD = os.environ.get("TARGET_PASSWORD", "YOUR_PASSWORD")

ADD_TO_CART = (By.XPATH, "//button[contains(normalize-space(.), 'Add to cart')]")
OUT_OF_STOCK = (
    By.XPATH,
    "//*[contains(normalize-space(.), 'Out of stock') or contains(normalize-space(.), 'Sold out')"
    " or contains(normalize-space(.), 'Currently unavailable')][not(*)]",
)


class TargetPokemonRestockMonitor:
    def __init__(self):
        self.driver = self._create_driver()
        self.wait = WebDriverWait(self.driver, 10)

    @staticmethod
    def _create_driver():
        """Create a Chrome driver; Selenium Manager resolves the driver binary."""
        logger.info("Setting up the Chrome webdriver...")
        options = webdriver.ChromeOptions()
        options.page_load_strategy = "eager"
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--window-size=1366,768")

        driver = webdriver.Chrome(options=options)
        # Applies to every new document, unlike a one-off execute_script call
        driver.execute_cdp_cmd(
            "Page.addScriptToEvaluateOnNewDocument",
            {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"},
        )
        return driver

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def check_stock(self, item):
        """Return True if the item appears to be in stock."""
        try:
            logger.info(f"Checking stock for {item['name']}...")
            self.driver.get(item["url"])
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
        """Log into the Target account. Return True on success."""
        try:
            logger.info("Attempting to login to Target account...")
            self.driver.get("https://www.target.com/account")

            email_field = self.wait.until(EC.element_to_be_clickable((By.ID, "username")))
            email_field.clear()
            email_field.send_keys(EMAIL)

            password_field = self.driver.find_element(By.ID, "password")
            password_field.clear()
            password_field.send_keys(PASSWORD)

            time.sleep(random.uniform(0.5, 1.5))
            self.driver.find_element(By.ID, "login").click()

            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "a[data-test*='account']"))
            )
            logger.info("Successfully logged in to Target account.")
            return True
        except TimeoutException:
            logger.error("Failed to login - timeout waiting for account element.")
            return False
        except WebDriverException as e:
            logger.error(f"Error during login: {e}")
            return False

    def add_to_cart(self, item):
        """Add the item to the cart. Return True on success."""
        try:
            logger.info(f"Attempting to add {item['name']} to cart...")
            if item["url"] not in self.driver.current_url:
                self.driver.get(item["url"])

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
            self.driver.get("https://www.target.com/co-cart")

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

        while True:
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
