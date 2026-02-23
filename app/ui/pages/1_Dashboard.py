import streamlit as st
import threading
import time

from app.core.credential_logic import profile_manager
from app.core.agentic_workflow import AGENT_STATE, launch_agent_thread
from app.core.db import get_all_jobs, init_db
from app.core.job_scraper import CompanyCrawler
import undetected_chromedriver as uc
from streamlit.runtime.scriptrunner import add_script_run_ctx
import pandas as pd

st.set_page_config(page_title="ApplyGenie Dashboard", page_icon="🧞‍♂️", layout="wide")

# Ensure the database and tables exist
init_db()

st.title("🧞‍♂️ ApplyGenie Autonomous Agent")
st.markdown("Deploy job applications on autopilot using DeepSeek-R1, DeepSeek-VL2, and Xvfb/noVNC.")

def init_scraper_driver():
    options = uc.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-gpu")
    return uc.Chrome(options=options, version_main=145)

# Initialize session state for UI updates
if "agent_running" not in st.session_state:
    st.session_state.agent_running = False

# Sidebar: Credentials & Profile setup
with st.sidebar:
    st.header("1. Your compliance profile")
    name = st.text_input("Full Name", value="John Doe")
    email = st.text_input("Email Address", value="johndoe@example.com")
    phone = st.text_input("Phone Number", value="555-123-4567")
    resume_text = st.text_area("Resume Content (Text)", height=200, value="Software Engineer with 5 years experience in Python and Docker.")
    
    st.subheader("Demographics")
    gender = st.selectbox("Gender", ["Male", "Female", "Decline to State"])
    race = st.selectbox("Race/Ethnicity", ["White", "Asian", "Black or African American", "Hispanic", "Decline to State"])
    veteran = st.selectbox("Veteran Status", ["I am not a protected veteran", "I identify as one or more of the classifications of a protected veteran", "Decline to state"])
    
    if st.button("Save Profile & Generate Master Password"):
        profile_data = {
            "name": name,
            "email": email,
            "phone": phone,
            "resume": resume_text,
            "gender": gender,
            "race": race,
            "veteran": veteran
        }
        profile_manager.save_profile(profile_data)
        st.success("Profile saved securely.")

    st.divider()
    
    # Master Password Display
    st.header("2. Master Password")
    pwd = profile_manager.get_master_password()
    st.code(pwd, language="text")
    st.caption("ApplyGenie uses this highly entropic password for all newly created accounts.")


# Main UI Dashboard
col1, col2 = st.columns([2, 1])

with col1:
    st.header("3. Auto-Hunter Mission Control")
    
    tab1, tab2, tab3 = st.tabs(["🎯 Scrape Jobs", "📋 Live Queue", "🤖 Agent Terminal"])
    
    with tab1:
        st.subheader("Fill the Queue (Universal Scraper)")
        
        st.markdown("Enter domains and keywords. The agent will find their Careers page, search, and queue the exact application links.")
        domains_input = st.text_input("Target Company Domains (Comma separated)", placeholder="netflix.com, anthropic.com")
        search_query = st.text_input("Target Job Keywords", placeholder="Lead AI Engineer, Machine Learning")
        
        if st.button("🔍 Autonomously Find & Queue Jobs", type="primary"):
            if not domains_input or not search_query:
                st.error("Please provide both target domains and keywords.")
            else:
                with st.spinner("Initializing autonomous crawler..."):
                    try:
                        driver = init_scraper_driver()
                        scraper = CompanyCrawler(driver)
                        
                        total_jobs = 0
                        domains = [d.strip() for d in domains_input.split(',')]
                        
                        for domain in domains:
                            st.toast(f"Crawling {domain}...")
                            found = scraper.find_and_queue_jobs(domain, search_query)
                            total_jobs += found
                            
                        driver.quit()
                        st.success(f"Crawler finished! Added {total_jobs} total jobs to the PENDING queue.")
                    except Exception as e:
                        st.error(f"Crawl failed: {e}")

    with tab2:
        st.subheader("Database Job Queue")
        
        # Action Bar
        c1, c2 = st.columns([1, 1])
        with c1:
            if st.button("▶️ Start Autonomous Worker", use_container_width=True):
                if not st.session_state.agent_running:
                    st.session_state.agent_running = True
                    AGENT_STATE["logs"].clear()
                    AGENT_STATE["status"] = "Listening to DB..."
                    
                    thread = threading.Thread(target=launch_agent_thread)
                    add_script_run_ctx(thread)
                    thread.daemon = True
                    thread.start()
                    st.rerun()
                    
        with c2:
            if st.button("🔄 Refresh DB", use_container_width=True):
                st.rerun()
        
        jobs = get_all_jobs()
        if not jobs:
            st.info("The database queue is currently empty. Use the Scrape Jobs tab to find applications.")
        else:
            # Convert to Pandas for pretty Streamlit rendering
            df = pd.DataFrame(jobs)
            # Reorder for readability
            df = df[['id', 'status', 'company', 'title', 'url', 'created_at']]
            
            # Styling colors based on status
            def color_status(val):
                color = 'gray'
                if val == 'PENDING': color = 'blue'
                elif val == 'IN_PROGRESS': color = 'orange'
                elif val == 'SUCCESS': color = 'green'
                elif val == 'FAILED': color = 'red'
                return f'color: {color}; font-weight: bold'
            
            st.dataframe(
                df.style.map(color_status, subset=['status']),
                hide_index=True,
                use_container_width=True,
                height=400
            )

    with tab3:
        st.subheader("Live Agent Thoughts")
        
        # Manual Intervention Block
        if AGENT_STATE["requires_manual_input"]:
            st.warning(f"⚠️ **MANUAL INTERVENTION REQUIRED**\\n\\n{AGENT_STATE['manual_input_prompt']}")
            user_input = st.text_input("Your Input:", key=f"manual_input_{len(AGENT_STATE['logs'])}")
            st.markdown("[▶️ View Browser in noVNC](http://localhost:8080) (Password: applygenie2026)")
            if st.button("Submit Input to Agent"):
                AGENT_STATE["manual_input_value"] = user_input
                st.rerun()

        # Dynamic status container
        if st.session_state.agent_running:
            status_container = st.empty()
            status_container.info(f"Current Status: **{AGENT_STATE['status']}**")
            
            log_container = st.empty()
            with log_container.container():
                for log in AGENT_STATE["logs"][-15:]:
                    st.text(f"> {log}")
            
            time.sleep(2)
            st.rerun()
        else:
            st.info("Worker thread is offline. Start it in the Live Queue tab.")

with col2:
    st.header("Visual Monitoring")
    st.markdown("""
    **The 'Watchable' Pod** allows you to see the Agent's raw X11 display.
    
    To view the browser live:
    1. Ensure Port `8080` is exposed on your RunPod config.
    2. Click the link below.
    3. Enter the VNC Password (`applygenie2026`).
    """)
    st.markdown("[📺 Open noVNC Viewer](http://localhost:8080)")
