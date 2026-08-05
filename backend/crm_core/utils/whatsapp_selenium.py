# crm_core/utils/whatsapp_selenium.py
import os
import time
import pyperclip
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import TimeoutException

CHROME_PROFILE_PATH = r"C:\Users\USER\whatsapp-chrome-profile"
os.makedirs(CHROME_PROFILE_PATH, exist_ok=True)
DEBUG_DIR = r"C:\Users\USER\whatsapp-debug"
os.makedirs(DEBUG_DIR, exist_ok=True)


def get_driver():
    options = webdriver.ChromeOptions()
    options.add_argument(f"user-data-dir={CHROME_PROFILE_PATH}")
    # Explicitly resolve chromedriver via webdriver-manager instead of
    # relying on Selenium's built-in auto-detection (Selenium Manager),
    # which was failing with "Unable to obtain driver for chrome" on
    # this machine. webdriver-manager downloads/caches the chromedriver
    # build that matches the installed Chrome version.
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    return driver


def _save_debug(driver, label):
    screenshot_path = os.path.join(DEBUG_DIR, f"{label}.png")
    html_path = os.path.join(DEBUG_DIR, f"{label}.html")
    try:
        driver.save_screenshot(screenshot_path)
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        print(f"Debug saved: {screenshot_path}")
        print(f"Debug saved: {html_path}")
    except Exception as e:
        print(f"Could not save debug info: {e}")


def send_whatsapp_group_message(group_name: str, message: str, timeout: int = 60):
    driver = get_driver()
    try:
        driver.get("https://web.whatsapp.com")
        time.sleep(8)
        try:
            search_box = WebDriverWait(driver, timeout).until(
                EC.presence_of_element_located(
                    (By.XPATH, '//input[contains(@placeholder,"Search")] | '
                               '//div[@contenteditable="true"][@data-tab="3"]')
                )
            )
        except TimeoutException:
            _save_debug(driver, "search_box_timeout")
            raise
        search_box.click()
        search_box.send_keys(group_name)
        time.sleep(2)

        # NOTE: neither clicking the inner <span title="..."> nor sending
        # ARROW_DOWN/ENTER to the search box reliably opens the chat on
        # WhatsApp Web — both were tested and the right-hand pane stayed
        # on the splash screen with no exception raised (the row just
        # never received the interaction). The fix: locate the actual
        # clickable row element and force-click it via JavaScript
        # (element.click() through execute_script), which bypasses
        # Selenium's native click — native clicks can be silently
        # swallowed by WhatsApp's virtualized list / overlapping
        # elements, while a JS-dispatched click still fires the
        # underlying React handler directly.
        try:
            row = WebDriverWait(driver, timeout).until(
                EC.presence_of_element_located(
                    (By.XPATH,
                     f'//span[@title="{group_name}"]'
                     '/ancestor::div[@role="listitem" or @role="row"][1]')
                )
            )
        except TimeoutException:
            _save_debug(driver, "row_not_found")
            raise

        driver.execute_script("arguments[0].scrollIntoView(true);", row)
        time.sleep(0.3)
        driver.execute_script("arguments[0].click();", row)
        time.sleep(2)

        # Verify the chat actually opened (chat header showing the group
        # name) before continuing — if it didn't, save debug info and
        # fail loudly instead of silently returning True.
        try:
            WebDriverWait(driver, timeout).until(
                EC.presence_of_element_located(
                    (By.XPATH, f'//header//span[@title="{group_name}"]')
                )
            )
        except TimeoutException:
            _save_debug(driver, "chat_did_not_open")
            raise TimeoutException(
                f"Clicked search result for '{group_name}' but the chat "
                "pane never opened (still showing splash screen)."
            )
        try:
            message_box = WebDriverWait(driver, timeout).until(
                EC.presence_of_element_located(
                    (By.XPATH, '//div[@contenteditable="true"][@data-tab="10"] | '
                               '//div[@contenteditable="true"][contains(@aria-label,"Type a message")] | '
                               '//div[@role="textbox"][contains(@aria-label,"Type a message")]')
                )
            )
        except TimeoutException:
            _save_debug(driver, "message_box_timeout")
            raise
        # send_keys() can't type emoji (outside the Unicode BMP), which
        # our message template relies on (🔔👤🏡📍📅📝✅📌). Instead,
        # copy the full message to the clipboard and paste it via
        # Ctrl+V — this preserves emoji and line breaks correctly.
        message_box.click()
        pyperclip.copy(message)
        time.sleep(0.5)
        message_box.send_keys(Keys.CONTROL, 'v')
        time.sleep(1)
        message_box.send_keys(Keys.ENTER)
        time.sleep(2)
        return True
    finally:
        driver.quit()
