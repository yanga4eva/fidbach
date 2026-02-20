import time
import logging
from typing import Optional, Dict

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import undetected_chromedriver as uc

from app.core.credential_logic import profile_manager

logger = logging.getLogger(__name__)

# --- Simplified Tool Functions for DeepSeek ---

def wait_for_element(driver: uc.Chrome, selector_value: str, by_method=By.XPATH, timeout=10):
    return WebDriverWait(driver, timeout).until(
        EC.presence_of_element_located((by_method, selector_value))
    )

def click_element(driver: uc.Chrome, xpath: str) -> str:
    """Clicks an element on the page using an XPath."""
    try:
        element = wait_for_element(driver, xpath, By.XPATH)
        # Scroll to it
        driver.execute_script("arguments[0].scrollIntoView(true);", element)
        time.sleep(0.5)
        element.click()
        time.sleep(2) # Wait for potential navigation or DOM changes
        return f"Successfully clicked element: {xpath}"
    except Exception as e:
        return f"Failed to click {xpath}. Error: {str(e)}"

def type_text(driver: uc.Chrome, text: str, xpath: str) -> str:
    """Types text into an input field defined by an XPath."""
    try:
        element = wait_for_element(driver, xpath, By.XPATH)
        driver.execute_script("arguments[0].scrollIntoView(true);", element)
        time.sleep(0.5)
        element.clear()
        element.send_keys(text)
        return f"Successfully typed text into: {xpath}"
    except Exception as e:
        return f"Failed to type into {xpath}. Error: {str(e)}"

def get_profile_data(field: str) -> str:
    """
    Retrieves a field from the user's profile.
    Available fields: name, email, phone, gender, race, veteran, resume, password
    """
    if field == "password":
        return profile_manager.get_master_password()
        
    profile = profile_manager.get_profile()
    return profile.get(field, f"[{field} not found in profile]")
