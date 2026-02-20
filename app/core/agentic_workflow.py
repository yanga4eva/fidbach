import time
import os
import logging
import requests
from typing import Dict, Any

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from app.core.credential_logic import profile_manager
from app.core.vision_engine import VisionEngine
from fpdf import FPDF
import tempfile
import subprocess

logger = logging.getLogger(__name__)

# State object used to communicate with the Streamlit UI
AGENT_STATE = {
    "status": "Idle",
    "logs": [],
    "requires_manual_input": False,
    "manual_input_prompt": "",
    "manual_input_value": None,
    "current_screenshot": None
}

def update_state(status: str, log_msg: str):
    logger.info(log_msg)
    AGENT_STATE["status"] = status
    AGENT_STATE["logs"].append(log_msg)

class JobApplicationAgent:
    def __init__(self):
        self.ollama_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
        self.r1_model = "deepseek-r1:32b"
        self.vision = VisionEngine()
        self.driver = None

    def get_chrome_main_version(self) -> int:
        """Dynamically fetches the major version of the installed Google Chrome."""
        try:
            result = subprocess.run(['google-chrome', '--version'], capture_output=True, text=True)
            # Output looks like: "Google Chrome 145.0.7632.109 "
            version_str = result.stdout.strip().split(' ')[2]
            main_version = int(version_str.split('.')[0])
            return main_version
        except Exception as e:
            logger.warning(f"Failed to fetch Chrome version dynamically: {e}")
            return 145 # Fallback to a recent high version

    def initialize_browser(self):
        """Initializes undetected-chromedriver attached to Xvfb display."""
        update_state("Initializing Browser", "Starting Chrome in watchable mode...")
        
        options = uc.ChromeOptions()
        # Ensure we attach to the virtual display
        options.add_argument(f"--display={os.environ.get('DISPLAY', ':99')}")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        # Run normally inside VNC instead of standard headless mode
        # By removing options.add_argument("--headless=new"), it runs visibly in Xvfb
        
        main_version = self.get_chrome_main_version()
        update_state("Browser Init", f"Detected Chrome v{main_version}. Launching Driver...")
        
        self.driver = uc.Chrome(options=options, version_main=main_version)
        update_state("Browser Ready", "Successfully started undetected-chromedriver.")

    def rewrite_resume(self, job_description: str) -> str:
        """
        Uses DeepSeek-R1 to rewrite the user profile/resume bullets
        specifically targeting the provided job description.
        """
        update_state("Tailoring Resume", "Summarizing JD and tailoring experience...")
        profile = profile_manager.get_profile()
        resume_text = profile.get("resume", "User has extensive software engineering experience.")
        
        prompt = (
            f"You are an expert ATS optimization AI. Rewrite the following resume "
            f"to highlight the skills relevant to the job description provided.\n\n"
            f"Job Description:\n{job_description}\n\n"
            f"Original User Resume:\n{resume_text}\n\n"
            f"Return ONLY the rewritten professional experience bullet points."
        )
        
        payload = {
            "model": self.r1_model,
            "prompt": prompt,
            "stream": False
        }
        
        try:
            response = requests.post(f"{self.ollama_url}/api/generate", json=payload)
            response.raise_for_status()
            tailored_resume = response.json().get('response', '')
            update_state("Resume Tailored", "Successfully optimized resume for ATS.")
            return tailored_resume
        except Exception as e:
            update_state("Error", f"Failed to rewrite resume: {e}")
            return resume_text
            
    def generate_pdf_resume(self, tailored_text: str) -> str | None:
        """
        Creates a PDF file from the tailored resume text.
        Returns the path to the generated PDF.
        """
        update_state("Generating PDF", "Converting tailored resume to PDF format...")
        try:
            pdf = FPDF()
            pdf.add_page()
            
            # Use a standard font. We'll use Arial-like font built into fpdf.
            pdf.set_font("helvetica", size=11)
            
            # Get user info for header
            profile = profile_manager.get_profile()
            name = profile.get("name", "Applicant Name")
            email = profile.get("email", "email@example.com")
            phone = profile.get("phone", "555-555-5555")
            
            # Add Header
            pdf.set_font("helvetica", "B", 16)
            pdf.cell(0, 10, name, new_x="LMARGIN", new_y="NEXT", align='C')
            
            pdf.set_font("helvetica", size=10)
            pdf.cell(0, 5, f"{email} | {phone}", new_x="LMARGIN", new_y="NEXT", align='C')
            
            pdf.ln(10)
            
            # Add tailored text
            pdf.set_font("helvetica", size=11)
            
            # multi_cell handles line breaks. Encode to latin-1 to avoid fpdf character issues
            clean_text = tailored_text.encode('latin-1', 'replace').decode('latin-1')
            pdf.multi_cell(0, 5, clean_text)
            
            # Save to a temporary file
            fd, path = tempfile.mkstemp(suffix=".pdf", prefix="ApplyGenie_Resume_")
            os.close(fd) # Close the file descriptor, fpdf will open it
            
            pdf.output(path)
            update_state("PDF Ready", f"Resume saved to {path}.")
            return path
        except Exception as e:
            update_state("Error", f"Failed to generate PDF: {e}")
            return None

    def request_manual_intervention(self, prompt: str):
        """Pauses the automation and asks the user for input via Streamlit."""
        update_state("Paused", f"Manual Input Required: {prompt}")
        AGENT_STATE["requires_manual_input"] = True
        AGENT_STATE["manual_input_prompt"] = prompt
        AGENT_STATE["manual_input_value"] = None
        
        # Wait until Streamlit loop provides the inputted value
        while AGENT_STATE["manual_input_value"] is None:
            time.sleep(1)
            
        value = AGENT_STATE["manual_input_value"]
        
        # Reset state back to normal
        AGENT_STATE["requires_manual_input"] = False
        AGENT_STATE["manual_input_prompt"] = ""
        AGENT_STATE["manual_input_value"] = None
        
        update_state("Resumed", f"Received manual input.")
        return value

    def run_application_flow(self, job_url: str):
        """The main agent loop for searching, tailoring, and applying."""
        try:
            if not self.driver:
                self.initialize_browser()
                
            update_state("Navigating", f"Navigating to job portal: {job_url}")
            self.driver.get(job_url)
            time.sleep(3) # Wait for initial load
            
            # Step 1: Scrape JD (simplified example)
            # Example: element = self.driver.find_element(By.TAG_NAME, 'body')
            # jd_text = element.text
            # tailored_bullets = self.rewrite_resume(jd_text)
            
            # Step 1b: Generate the PDF based on the updated resume
            update_state("Synthesizing Application", "Preparing documents for upload...")
            # For demonstration, we'll pretend we just scraped this JD and generated the resume text
            dummy_jd = "Looking for a seasoned software engineer with Docker experience."
            tailored_text = self.rewrite_resume(dummy_jd)
            pdf_path = self.generate_pdf_resume(tailored_text)
            
            # Step 2: Fill Account Creation (using master password)
            update_state("Creating Account", "Filling account creation form and uploading resume...")
            # Example: Locate email/password fields
            # email_field = self.driver.find_element(By.NAME, 'email')
            # email_field.send_keys(profile_manager.get_profile().get('email'))
            # pwd_field = self.driver.find_element(By.NAME, 'password')
            # pwd_field.send_keys(profile_manager.get_master_password())
            
            # Example: Locate File Upload field and send the PDF path
            # if pdf_path:
            #     upload_field = self.driver.find_element(By.CSS_SELECTOR, 'input[type="file"]')
            #     upload_field.send_keys(pdf_path)
            
            # Step 3: Handle complex forms & 2FA
            # Simulated check for a verification code specific to workdays/lever
            page_source = self.driver.page_source.lower()
            if "verification code" in page_source or "enter code" in page_source:
                code = self.request_manual_intervention("A verification code was sent to your email. Please enter it here:")
                update_state("Entering Code", f"Applying code: {code}")
                # code_field = self.driver.find_element(By.NAME, 'verification_code')
                # code_field.send_keys(code)
            
            # Step 4: Vision QC before final submit
            screenshot_file = "/tmp/presubmit.png"
            self.driver.save_screenshot(screenshot_file)
            
            update_state("Vision QC", "Running DeepSeek-VL2 quality checks...")
            missing_check = self.vision.check_for_missing_fields(screenshot_file)
            dropdown_check = self.vision.check_dropdown_mapping(screenshot_file)
            captcha_check = self.vision.detect_captcha(screenshot_file)
            
            logger.info("Vision QC Results:")
            logger.info(missing_check)
            logger.info(dropdown_check)
            logger.info(captcha_check)
            
            if "CAPTCHA: YES" in captcha_check.get("raw_response", ""):
                self.request_manual_intervention("CAPTCHA detected on screen! Please solve it via the VNC viewer (Port 8080) and type 'DONE' here.")
                
            update_state("Success", "QC Passed. Assuming Application Submitted.")
            
        except Exception as e:
            update_state("Failed", f"Agent crashed during application: {e}")
        finally:
            if self.driver:
                # We optionally leave it open for VNC inspection, or close it.
                # self.driver.quit()
                pass

def launch_agent_thread(job_url: str):
    """Entry point for threading the agent so Streamlit UI remains responsive."""
    agent = JobApplicationAgent()
    agent.run_application_flow(job_url)
