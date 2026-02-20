import streamlit as st

st.set_page_config(page_title="ApplyGenie Home", page_icon="🧞‍♂️", layout="centered")

# --- Hero Section ---
st.markdown("<h1 style='text-align: center; color: #4A90E2;'>🧞‍♂️ ApplyGenie</h1>", unsafe_allow_html=True)
st.markdown("<h3 style='text-align: center;'>Your Autonomous Job Application Surrogate</h3>", unsafe_allow_html=True)
st.divider()

# --- Value Proposition ---
col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("### 🧠 Smart Tailoring")
    st.write("Driven by **DeepSeek-R1 (32B)**, ApplyGenie reads the target Job Description and rewrites your resume bullets on-the-fly to bypass ATS filters.")

with col2:
    st.markdown("### 👀 Visual QA")
    st.write("Powered by **LLaVA (7B)** Vision, the agent physically 'looks' at the browser to catch missing required fields, map complex dropdowns, and spot CAPTCHAs before clicking submit.")

with col3:
    st.markdown("### 🔒 Secure Surrogate")
    st.write("ApplyGenie generates a high-entropy 16-character Master Password for every application it submits, ensuring your personal credentials are never exposed or reused.")

st.divider()

# --- Get Started ---
st.markdown("<h3 style='text-align: center;'>Ready to automate your job hunt?</h3>", unsafe_allow_html=True)

col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    st.info("👈 Click **1_Dashboard** in the sidebar to configure your profile and launch your first mission!")
    
    st.markdown("#### 📺 Visual Monitoring")
    st.write("Want to watch the agent work in real-time?")
    st.markdown("[Open noVNC Watchable Pod](http://localhost:8080) (Password: `applygenie2026`)")

st.divider()
st.caption("ApplyGenie is an open-source autonomous agent designed for RunPod GPU deployments.")
