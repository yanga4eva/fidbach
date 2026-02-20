import streamlit as st
import threading
import time

from app.core.credential_logic import profile_manager
from app.core.agentic_workflow import AGENT_STATE, launch_agent_thread
from streamlit.runtime.scriptrunner import add_script_run_ctx

st.set_page_config(page_title="ApplyGenie Dashboard", page_icon="🧞‍♂️", layout="wide")

st.title("🧞‍♂️ ApplyGenie Autonomous Agent")
st.markdown("Deploy job applications on autopilot using DeepSeek-R1, DeepSeek-VL2, and Xvfb/noVNC.")

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
    st.header("3. Mission Control")
    job_url = st.text_input("Target Job Application URL", placeholder="https://jobs.lever.co/example/1234")
    
    if st.button("🚀 Launch ApplyGenie", use_container_width=True, type="primary"):
        if not st.session_state.agent_running:
            st.session_state.agent_running = True
            AGENT_STATE["logs"].clear()
            AGENT_STATE["status"] = "Starting"
            
            # Start the agent in a background thread
            thread = threading.Thread(target=launch_agent_thread, args=(job_url,))
            add_script_run_ctx(thread)
            thread.daemon = True
            thread.start()
            st.rerun()

    # Dynamic status container
    st.subheader("Agent Activity Log")
    log_container = st.empty()
    status_container = st.empty()
    
    # Manual Intervention Block
    if AGENT_STATE["requires_manual_input"]:
        st.warning(f"⚠️ **MANUAL INTERVENTION REQUIRED**\n\n{AGENT_STATE['manual_input_prompt']}")
        user_input = st.text_input("Your Input:", key=f"manual_input_{len(AGENT_STATE['logs'])}")
        
        # Link to VNC
        st.markdown("[▶️ View Browser in noVNC](http://localhost:8080) (Password: applygenie2026)")
        
        if st.button("Submit Input to Agent"):
            AGENT_STATE["manual_input_value"] = user_input
            st.rerun()

    # Simple auto-refresh for the logs if running
    if st.session_state.agent_running:
        with log_container.container():
            for log in AGENT_STATE["logs"][-10:]: # Show last 10 logs
                st.text(f"> {log}")
        
        status_container.info(f"Current Status: **{AGENT_STATE['status']}**")
        
        if AGENT_STATE["status"] in ["Success", "Failed"]:
            st.session_state.agent_running = False
        else:
            time.sleep(1)
            st.rerun()

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
