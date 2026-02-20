import time
import logging
from typing import Optional, Dict

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import undetected_chromedriver as uc

from app.core.credential_logic import profile_manager
from app.core.vision_engine import VisionEngine

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
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
        time.sleep(0.5)
        # Use javascript click to bypass any overlapping elements or modals
        driver.execute_script("arguments[0].click();", element)
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

def look_at_screen(driver: uc.Chrome, vision_engine: VisionEngine, question: str) -> str:
    """
    Takes a screenshot of the current browser and asks the LLaVA vision model a question about it.
    """
    try:
        screenshot_path = "/tmp/agent_vision_req.png"
        driver.save_screenshot(screenshot_path)
        
        # We bypass the specific prompt helpers and hit the internal runner directly
        # so the agent can ask custom questions
        result = vision_engine._run_vision_prompt(screenshot_path, question)
        
        if result["success"]:
            return f"Vision Analysis: {result['raw_response']}"
        else:
            return f"Vision Error: {result['error']}"
    except Exception as e:
        return f"Failed to capture screen: {str(e)}"

def scroll_down(driver: uc.Chrome) -> str:
    """Scrolls down the page by one viewport height."""
    try:
        driver.execute_script("window.scrollBy(0, window.innerHeight);")
        time.sleep(1)
        return "Successfully scrolled down."
    except Exception as e:
        return f"Failed to scroll down: {str(e)}"

def scroll_up(driver: uc.Chrome) -> str:
    """Scrolls up the page by one viewport height."""
    try:
        driver.execute_script("window.scrollBy(0, -window.innerHeight);")
        time.sleep(1)
        return "Successfully scrolled up."
    except Exception as e:
        return f"Failed to scroll up: {str(e)}"

def go_back(driver: uc.Chrome) -> str:
    """Navigates back to the previous page in history."""
    try:
        driver.back()
        time.sleep(2)
        return "Successfully navigated back."
    except Exception as e:
        return f"Failed to navigate back: {str(e)}"
