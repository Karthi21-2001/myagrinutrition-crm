# crm_core/utils/whatsapp_selenium.py
#
# Adapted from the original local/Windows version to run inside a
# Docker container on Render, under a virtual display (Xvfb) rather
# than a real monitor. Key differences from the original, and why:
#
# 1. CHROME_PROFILE_PATH / DEBUG_DIR are now read from environment
#    variables instead of hardcoded Windows paths. CHROME_PROFILE_PATH
#    MUST point at a Render persistent disk mount (e.g. /var/data/...)
#    or the WhatsApp Web login is wiped on every deploy/restart and
#    you're back to scanning a QR code every time.
#
# 2. Chrome/driver binary locations are set explicitly
#    (options.binary_location + Service executable_path) because the
#    Docker image installs `chromium` + `chromium-driver` via apt,
#    which don't live at Selenium's default lookup paths.
#
# 3. --no-sandbox / --disable-dev-shm-usage are required when Chrome
#    runs as root inside a container — without them Chrome crashes on
#    startup.
#
# 4. A file lock (via the `filelock` package) wraps the whole send,
#    so two "Notify" clicks in quick succession can't launch two
#    Chrome instances against the same profile directory at once
#    (this corrupts the profile / crashes both).
#
# 5. Deliberately NOT using `--headless` — WhatsApp Web's JS often
#    behaves differently (or refuses to fully load) in Chrome's
#    headless mode. Instead this runs a normal (headful) Chrome
#    pointed at the virtual display Xvfb provides via the DISPLAY
#    env var set in entrypoint.sh. From Chrome's point of view it's
#    talking to a real screen.

import os
import time
import pyperclip
from filelock import FileLock, Timeout
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import TimeoutException

# Persistent disk mount point on Render — set this to whatever mount
# path you configure when you attach the disk in the Render dashboard
# (their docs default to /var/data). Falls back to a local ./data
# folder so this still runs fine on your own machine for testing.
DATA_ROOT = os.environ.get("WHATSAPP_DATA_ROOT", "./data")

CHROME_PROFILE_PATH = os.environ.get(
    "WHATSAPP_CHROME_PROFILE_PATH",
    os.path.join(DATA_ROOT, "whatsapp-chrome-profile"),
)
os.makedirs(CHROME_PROFILE_PATH, exist_ok=True)

# Debug screenshots/HTML don't need to survive a restart, so these can
# live on ephemeral container storage (/tmp) unless you want to keep
# a history of failures — in which case point this at DATA_ROOT too.
DEBUG_DIR = os.environ.get("WHATSAPP_DEBUG_DIR", "/tmp/whatsapp-debug")
os.makedirs(DEBUG_DIR, exist_ok=True)

CHROME_BINARY = os.environ.get("CHROME_BINARY_PATH", "/usr/bin/chromium")
CHROMEDRIVER_BINARY = os.environ.get("CHROMEDRIVER_PATH", "/usr/bin/chromedriver")

# Prevents two simultaneous notify requests from launching two Chrome
# instances against the same profile directory. lock file lives next
# to the profile itself (also on the persistent disk).
_LOCK_PATH = os.path.join(CHROME_PROFILE_PATH, "..", "whatsapp_send.lock")
_LOCK_TIMEOUT_SECONDS = 90  # give a prior in-flight send time to finish


def get_driver():
    options = webdriver.ChromeOptions()
    options.add_argument(f"user-data-dir={CHROME_PROFILE_PATH}")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1280,1696")
    options.binary_location = CHROME_BINARY

    service = Service(executable_path=CHROMEDRIVER_BINARY)
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


def is_logged_in(timeout: int = 15) -> bool:
    """Quick check used by the QR-login bootstrap view: opens WhatsApp
    Web and reports whether the profile already has an active session
    (search box present) rather than showing a QR code. Does not send
    anything.
    """
    driver = get_driver()
    try:
        driver.get("https://web.whatsapp.com")
        time.sleep(5)
        try:
            WebDriverWait(driver, timeout).until(
                EC.presence_of_element_located(
                    (By.XPATH, '//div[@contenteditable="true"][@data-tab="3"]')
                )
            )
            return True
        except TimeoutException:
            return False
    finally:
        driver.quit()


def send_whatsapp_group_message(group_name: str, message: str, timeout: int = 60):
    lock = FileLock(_LOCK_PATH)
    try:
        with lock.acquire(timeout=_LOCK_TIMEOUT_SECONDS):
            return _send_whatsapp_group_message(group_name, message, timeout)
    except Timeout:
        raise RuntimeError(
            "Another WhatsApp notification is already in progress — try again shortly."
        )


def _send_whatsapp_group_message(group_name: str, message: str, timeout: int):
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
            # Most likely cause on a fresh/expired session: no logged-in
            # WhatsApp Web session on this profile. Surface that clearly
            # instead of a bare Selenium timeout.
            raise RuntimeError(
                "WhatsApp Web isn't logged in on the server session. "
                "An admin needs to visit the QR login page to re-authenticate."
            )
        search_box.click()
        search_box.send_keys(group_name)
        time.sleep(2)
        try:
            chat = WebDriverWait(driver, timeout).until(
                EC.element_to_be_clickable(
                    (By.XPATH, f'//span[@title="{group_name}"]')
                )
            )
        except TimeoutException:
            _save_debug(driver, "chat_click_timeout")
            raise RuntimeError(f'Could not find a WhatsApp group named "{group_name}".')
        chat.click()
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
        # Ctrl+V. On Linux this routes through xclip against the Xvfb
        # display — make sure xclip is installed in the image (see
        # Dockerfile) or pyperclip raises PyperclipException here.
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
