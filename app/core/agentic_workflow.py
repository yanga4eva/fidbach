import time
import os
import logging
import requests
from typing import Dict, Any

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import UnexpectedAlertPresentException, NoAlertPresentException

from app.core.credential_logic import profile_manager
from app.core.vision_engine import VisionEngine
from app.core.db import get_next_pending_job, update_job_status
import app.core.tools as agent_tools
from app.core.som_injector import inject_and_get_map, trigger_click_by_id, trigger_type_by_id, trigger_upload_by_id

from fpdf import FPDF
import tempfile
import subprocess

# LangChain Imports
from langchain_community.llms import Ollama
from langchain_core.tools import Tool
from langchain.agents import AgentExecutor, create_react_agent
from langchain.prompts import PromptTemplate

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
            
    def infer_answer_from_resume(self, question: str) -> str:
        """
        Uses DeepSeek-R1 internally to deduce the answer to a specific HR question
        (e.g., 'Years of Python experience?') based on the user's resume.
        """
        update_state("Inferring Answer", f"Checking resume for: {question}")
        profile = profile_manager.get_profile()
        resume_text = profile.get("resume", "User has extensive software engineering experience.")
        
        prompt = (
            f"You are an expert HR assistant. Based on the following User Resume, answer the specific question.\n"
            f"Question: {question}\n\n"
            f"Resume:\n{resume_text}\n\n"
            f"Return ONLY the concise text/number answer. Do not include your reasoning or `<think>` blocks in the final output string if you can strip them, just the plain answer."
        )
        
        payload = {
            "model": self.r1_model,
            "prompt": prompt,
            "stream": False
        }
        
        try:
            response = requests.post(f"{self.ollama_url}/api/generate", json=payload)
            response.raise_for_status()
            answer = response.json().get('response', '')
            # Try to strip out <think> tags if they exist in the raw text
            import re
            answer = re.sub(r'<think>.*?</think>', '', answer, flags=re.DOTALL).strip()
            return answer
        except Exception as e:
            logger.error(f"Failed to infer answer: {e}")
            return "Unable to determine from resume."

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

    def run_application_flow(self, job_url: str) -> bool:
        """
        The main agent loop for navigating and applying.
        Returns True if successful (Agent Finished with positive final answer), False if failed/timeout.
        """
        try:
            if not self.driver:
                self.initialize_browser()
                
            update_state("Navigating", f"Navigating to job portal: {job_url}")
            self.driver.get(job_url)
            time.sleep(3) # Wait for initial load
            
            # --- 0. Pre-Flight Checks (Dismiss Login Walls) ---
            update_state("Pre-flight", "Checking for intrusive login walls...")
            try:
                # LinkedIn often throws a "Sign in" modal that blocks the entire screen.
                # The close button usually has an aria-label="Dismiss"
                dismiss_btn = self.driver.find_element(By.CSS_SELECTOR, "button[aria-label='Dismiss']")
                if dismiss_btn:
                    # Use javascript to click it in case another element is slightly overlapping
                    self.driver.execute_script("arguments[0].click();", dismiss_btn)
                    update_state("Login Wall Dismissed", "Successfully closed the LinkedIn sign-in modal.")
                    time.sleep(1)
            except Exception:
                pass # Modal not found, safe to proceed
            
            # --- 1. Set up LangChain LLM ---
            llm = Ollama(model=self.r1_model, base_url=self.ollama_url)
            
            # --- 2. Define Tools ---
            # We use a mutable state wrapper to pass the most recent SOM map into the tools
            current_state = {"som_map": {}}
            
            tools = [
                Tool(
                    name="Click_Element_By_ID",
                    func=lambda node_id: trigger_click_by_id(self.driver, current_state["som_map"], node_id.strip()),
                    description="Clicks an interactive element. Input MUST be just the numeric ID (e.g., '42')."
                ),
                Tool(
                    name="Type_Text_By_ID",
                    func=lambda args: trigger_type_by_id(self.driver, current_state["som_map"], args.split('|')[0].strip(), args.split('|')[1]),
                    description="Types text into an input field. Input must be formatted exactly as 'id|text_to_type' (e.g., '12|John')."
                ),
                Tool(
                    name="Upload_File_By_ID",
                    func=lambda args: trigger_upload_by_id(self.driver, current_state["som_map"], args.split('|')[0].strip(), args.split('|')[1]),
                    description="Uploads a file to an <input type='file'> element natively. Input must be formatted exactly as 'id|file_path' (e.g., '12|/tmp/resume.pdf')."
                ),
                Tool(
                    name="Get_Profile_Data",
                    func=agent_tools.get_profile_data,
                    description="Fetches standard user profile data. Input MUST be exactly one of: name, email, phone, resume, password."
                ),
                Tool(
                    name="Infer_Answer",
                    func=self.infer_answer_from_resume,
                    description="Queries the User's Resume to find the answer to specific/complex HR questions (e.g., 'How many years of Python experience do you have?'). Input is the exact question text on the screen."
                ),
                Tool(
                    name="Pause_For_Human",
                    func=self.request_manual_intervention,
                    description="Pauses the agent and asks the user for help (e.g., for CAPTCHAs, 2FA, or unknown screens). Input is the prompt/question to ask the user."
                ),
                Tool(
                    name="Scroll_Down",
                    func=lambda _: agent_tools.scroll_down(self.driver),
                    description="Scrolls down the page by one viewport height. Use this if you need to see more of a long form. Input should be 'down'."
                ),
                Tool(
                    name="Scroll_Up",
                    func=lambda _: agent_tools.scroll_up(self.driver),
                    description="Scrolls up the page by one viewport height. Input should be 'up'."
                ),
                Tool(
                    name="Go_Back",
                    func=lambda _: agent_tools.go_back(self.driver),
                    description="Clicks the browser's back button to navigate to the previous page. Input should be 'back'."
                )
            ]
            
            # --- 3. Define ReAct Prompt ---
            template = '''Answer the following questions as best you can. You have access to the following tools:

{tools}

You are an autonomous Job Application Agent. Your goal is to navigate the webpage, fill out the entire multi-page application form, and click Submit until the application is 100% completed.
Look at the CURRENT INTERACTIVE ELEMENTS map and the CURRENT VISUAL SUMMARY below. 
Find the numeric ID for the inputs you need to fill, or the button you need to click to advance.

CRITICAL INSTRUCTION: You MUST ONLY interact with elements that have a numeric ID listed in the Interactive Elements map below. DO NOT guess or hallucinate IDs. 

INTERSTITIAL INSTRUCTION: If you see a 'Accept Cookies', 'Close', or 'No Thanks' button for a non-application popup, execute Click_Element_By_ID on it immediately to clear the screen.

AUTH INSTRUCTION: If prompted to 'Sign In', SECONDS before creating a new account, scan the Interactive Elements for an 'Apply as Guest', 'Quick Apply', or 'Autofill with Resume' button. ALWAYS prefer Guest checkout over Account Creation. If Login/Register is mandatory, find the "Create Account" or "Register" button and click it to start a new flow using the `Get_Profile_Data` tools.

MULTI-STEP INSTRUCTION: If you see 'Next' or 'Continue', you are in a multi-step form. Click it, wait for the page to load, and continue filling fields. Do not output Final Answer.

ERROR HANDLING: If the VISUAL SUMMARY specifically mentions 'Red Error Text' or missing fields, you MUST fix those specific fields before clicking Next or Submit again.

CRITICAL END-STATE INSTRUCTION: DO NOT output a 'Final Answer' unless you physically see a confirmation message on the screen stating the application was submitted (e.g., "Application Complete", "Success", "Thank you for applying"). Your Final Answer MUST include the exact text of the success confirmation message.

CURRENT INTERACTIVE ELEMENTS:
{interactive_elements}

CURRENT VISUAL SUMMARY (From LLaVA):
{vision_summary}

Use the following format:

Question: the input question you must answer
Thought: you should always think about what to do
Action: the action to take, should be one of [{tool_names}]
Action Input: the input to the action
Observation: the result of the action
... (this Thought/Action/Action Input/Observation can repeat N times)
Thought: I now know the final answer
Final Answer: the final answer to the original input question

Begin!

Question: {input}
Thought:{agent_scratchpad}'''

            prompt = PromptTemplate.from_template(template)
            
            # --- 4. Initialize Agent Object ---
            agent = create_react_agent(llm, tools, prompt)
            
            # --- 5. Custom Orchestrator Loop ---
            update_state("Agent Loop Started", "Analyzing the DOM and reasoning next steps...")
            
            agent_scratchpad = ""
            max_iterations = 50  # Increased for multi-page complex applications
            
            for i in range(max_iterations):
                update_state(f"Step {i+1}/{max_iterations}", "Perceiving Screen (DOM + Vision)...")
                
                # Handle Alerts before proceeding
                try:
                    # Just touching driver.title forces an alert check
                    _ = self.driver.title 
                except UnexpectedAlertPresentException:
                    alert = self.driver.switch_to.alert
                    alert_text = alert.text
                    update_state("Alert Detected", f"Handling unexpected JS alert: {alert_text}")
                    alert.accept() # Dismiss the alert
                    
                    # Feed this back to the loop immediately
                    agent_scratchpad += f"\nObservation: A JavaScript Alert popped up with message: '{alert_text}'. I just dismissed it. I need to fix this error before advancing.\nThought: "
                    time.sleep(1)
                    continue
                
                # Retrieve Set-Of-Mark IDs and Draw Visual Boxes
                raw_som_map = inject_and_get_map(self.driver)
                current_state["som_map"] = raw_som_map
                
                # Convert the raw JSON map into an ultra-compressed string for the LLM context
                compact_elements = []
                for node_id, data in raw_som_map.items():
                    tag = data.get('tagName', 'UNKNOWN')
                    text = data.get('text', '').replace('\\n', ' ')[:50]
                    aria = data.get('ariaLabel', '')[:50]
                    compact_elements.append(f"[{node_id}] {tag} | Text: '{text}' | Aria: '{aria}'")
                elements_string = "\\n".join(compact_elements)
                if not elements_string:
                    elements_string = "No interactive elements found."
                
                # Retrieve Fresh Vision (Screenshot now includes the red SOM bounding boxes!)
                screenshot_path = "/tmp/agent_vision_loop.png"
                self.driver.save_screenshot(screenshot_path)
                vision_req = "Describe the interactive layout of this page. You see red bounding boxes with numbers inside them. What form fields or buttons are visible (mention their numeric IDs)? CRITICAL: Are there any red error texts or highlighted required fields on this form? If so, list them explicitly."
                vision_res = self.vision._run_vision_prompt(screenshot_path, vision_req)
                vision_summary = vision_res.get('raw_response', 'Failed to get vision summary.')
                
                # Execute ONE step of the ReAct Agent
                try:
                    response = agent.invoke({
                        "input": "What is the next immediate action required to progress this job application? Output an Action if there is work to do. Output Final Answer ONLY IF the screen explicitly confirms the application is fully submitted.",
                        "interactive_elements": elements_string,
                        "vision_summary": vision_summary,
                        "agent_scratchpad": agent_scratchpad,
                        "intermediate_steps": [] # Required by LangChain internals
                    })
                except Exception as parse_error:
                    update_state("Parsing Error", f"Agent output format issue: {parse_error}")
                    # Feed the parsing error back as an observation so the LLM corrects its formatting
                    observation = f"Failed to parse LLM output. You MUST only output one Action and Action Input string. Error: {str(parse_error)}"
                    agent_scratchpad += f"\nObservation: {observation}\nThought: "
                    time.sleep(2)
                    continue

                
                # Process the Agent Action
                # LangChain's create_react_agent returns AgentAction or AgentFinish
                from langchain_core.agents import AgentAction, AgentFinish
                
                if isinstance(response, AgentFinish):
                    update_state("Agent Finished", f"Final Output: {response.return_values['output']}")
                    return True
                elif isinstance(response, AgentAction):
                    action = response
                    tool_name = action.tool
                    tool_input = action.tool_input
                    
                    update_state("Executing Action", f"Tool: {tool_name} | Input: {tool_input}")
                    
                    # Find and execute the actual tool
                    tool_obj = next((t for t in tools if t.name == tool_name), None)
                    if tool_obj:
                        observation = tool_obj.func(tool_input)
                    else:
                        observation = f"Tool {tool_name} not found."
                    
                    # Store history for the scratchpad
                    agent_scratchpad += f"\nAction: {tool_name}\nAction Input: {tool_input}\nObservation: {observation}\nThought: "
                    time.sleep(2) # Wait for page reaction
            else:
                update_state("Timeout", "Agent hit maximum iterations without finishing.")
                return False
            
        except Exception as e:
            update_state("Failed", f"Agent crashed during application: {e}")
            return False
        finally:
            if self.driver:
                pass
            return False

def launch_agent_thread(_unused: str = ""):
    """
    Entry point for threading the agent.
    Acts as an infinite consumer loop, pulling PENDING jobs from SQLite.
    """
    agent = JobApplicationAgent()
    update_state("Worker Started", "Agent worker thread is online. Waiting for jobs in the queue...")
    
    while True:
        job = get_next_pending_job()
        if job:
            job_id = job['id']
            url = job['url']
            update_state("Job Pulled", f"Starting Application for: {job['title']} at {job['company']}")
            
            # Run the agent
            success = agent.run_application_flow(url)
            
            # Update DB
            if success:
                update_job_status(job_id, "SUCCESS", "Application completed successfully.")
            else:
                # If it failed, restart the browser session so the next job has a clean slate
                if agent.driver:
                    agent.driver.quit()
                    agent.driver = None
                update_job_status(job_id, "FAILED", "Agent timed out or crashed.")
                
        else:
            time.sleep(5) # Poll every 5 seconds if queue is empty

