import base64
import os
import requests
import logging

logger = logging.getLogger(__name__)

class VisionEngine:
    """
    Handles quality checks using DeepSeek-VL2 before submitting job applications.
    """
    def __init__(self, ollama_url: str = ""):
        if not ollama_url:
            self.ollama_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
        else:
            self.ollama_url = ollama_url
            # We use llava:7b as the official vision model for Ollama
        self.generate_api_url = f"{self.ollama_url}/api/generate"
        self.model = "llava:7b"

    def _encode_image(self, image_path: str) -> str:
        """Encodes an image to base64 for Ollama API."""
        with open(image_path, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
        return encoded_string

    def check_for_missing_fields(self, screenshot_path: str) -> dict:
        """
        Analyzes a screenshot to see if there are missing required fields,
        typically indicated by red text or asterisks next to empty boxes.
        """
        prompt = (
            "Analyze this job application form screenshot. "
            "Are there any missing required fields indicated by red error text, "
            "or empty text boxes that have a red asterisk next to them? "
            "Reply with 'STATUS: OK' if there are no errors, or list the specific fields that are missing."
        )
        return self._run_vision_prompt(screenshot_path, prompt)

    def check_dropdown_mapping(self, screenshot_path: str) -> dict:
        """
        Verifies if dropdowns (like Ethnicity or Gender) appear to be incorrectly 
        mapped based on visible selections.
        """
        prompt = (
            "Analyze this job application form screenshot focusing on the dropdown fields "
            "such as 'Gender', 'Race/Ethnicity', and 'Veteran Status'. "
            "Does the selected option match the category? (e.g., 'Asian' shouldn't be under 'Gender'). "
            "Reply with 'STATUS: OK' if everything looks correct, or state what is misconfigured."
        )
        return self._run_vision_prompt(screenshot_path, prompt)

    def detect_captcha(self, screenshot_path: str) -> dict:
        """
        Detects if a CAPTCHA is visible on the screen and requires manual intervention.
        """
        prompt = (
            "Is there an active, unsolved CAPTCHA block explicitly visible on this screen right now? "
            "Look for 'I am not a robot. reCAPTCHA', or an image selection puzzle. "
            "Reply with 'CAPTCHA: YES' ONLY if you are absolutely certain one is visible and blocking progress. "
            "Otherwise reply 'CAPTCHA: NO'."
        )
        return self._run_vision_prompt(screenshot_path, prompt)

    def _run_vision_prompt(self, screenshot_path: str, prompt: str) -> dict:
        """Internal helper to execute a vision prompt against Ollama."""
        try:
            b64_img = self._encode_image(screenshot_path)
            
            payload = {
                "model": self.model,
                "prompt": prompt,
                "images": [b64_img],
                "stream": False
            }
            
            response = requests.post(self.generate_api_url, json=payload)
            response.raise_for_status()
            
            result = response.json()
            response_text = result.get('response', '')
            
            logger.info(f"Vision analysis completed for {screenshot_path}.")
            
            return {
                "success": True,
                "raw_response": response_text
            }
        except Exception as e:
            logger.error(f"Error communicating with vision model: {e}")
            return {
                "success": False,
                "error": str(e)
            }
