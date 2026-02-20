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
from app.core.dom_parser import compress_dom
import app.core.tools as agent_tools

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
        """The main agent loop for searching, tailoring, and applying using LangChain ReAct."""
        try:
            if not self.driver:
                self.initialize_browser()
                
            update_state("Navigating", f"Navigating to job portal: {job_url}")
            self.driver.get(job_url)
            time.sleep(3) # Wait for initial load
            
            # --- 1. Set up LangChain LLM ---
            llm = Ollama(model=self.r1_model, base_url=self.ollama_url)
            
            # --- 2. Define Tools ---
            tools = [
                Tool(
                    name="Click_Element",
                    func=lambda xpath: agent_tools.click_element(self.driver, xpath),
                    description="Clicks an interactive element on the page. Input should be a valid XPath."
                ),
                Tool(
                    name="Type_Text",
                    func=lambda args: agent_tools.type_text(self.driver, text=args.split('|')[1], xpath=args.split('|')[0]),
                    description="Types text into an input field. Input must be formatted exactly as 'xpath|text_to_type'."
                ),
                Tool(
                    name="Get_Profile_Data",
                    func=agent_tools.get_profile_data,
                    description="Fetches user profile data to fill forms. Input should be exactly one of: name, email, phone, resume, password."
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

You are an autonomous Job Application Agent. Look at the CURRENT SCREEN DOM and the CURRENT VISUAL SUMMARY below. 
Find the XPath for the inputs you need to fill, or the button you need to click to advance.

CURRENT SCREEN DOM:
{current_dom}

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
                
                # Retrieve Fresh DOM
                raw_html = self.driver.page_source
                clean_dom = compress_dom(raw_html)
                
                # Retrieve Fresh Vision
                screenshot_path = "/tmp/agent_vision_loop.png"
                self.driver.save_screenshot(screenshot_path)
                vision_req = "Describe this page. Are there any forms, buttons, CAPTCHAs, or error messages?"
                vision_res = self.vision._run_vision_prompt(screenshot_path, vision_req)
                vision_summary = vision_res.get('raw_response', 'Failed to get vision summary.')
                
                # Execute ONE step of the ReAct Agent
                try:
                    response = agent.invoke({
                        "input": "Look at the DOM and Visual Summary. Execute the next necessary action to progress the job application, or output Final Answer if submitted.",
                        "current_dom": clean_dom,
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
                    break
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
            
        except Exception as e:
            update_state("Failed", f"Agent crashed during application: {e}")
        finally:
            if self.driver:
                pass

def launch_agent_thread(job_url: str):
    """Entry point for threading the agent so Streamlit UI remains responsive."""
    agent = JobApplicationAgent()
    agent.run_application_flow(job_url)
