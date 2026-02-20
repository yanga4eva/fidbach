# ApplyGenie Walkthrough

This document outlines the architecture, deployment, and usage of the ApplyGenie autonomous job application agent.

## Architecture Overview

ApplyGenie is designed to run efficiently on GPU instances like RunPod, relying on a fully containerized "Watchable Pod" architecture.

### Key Components:
- **Xvfb & noVNC**: Provides a virtual frame buffer (`:99`) allowing the `undetected-chromedriver` to run visibly in the cloud. You can monitor the agent's actions securely via a password-protected web VNC client on port `8080`.
- **DeepSeek-R1 (32B)**: Driven by Ollama, this model is responsible for parsing Job Descriptions and intelligently rewriting the user's resume bullet points to bypass ATS filters.
- **PDF Resume Engine**: The agent dynamically generates a compiled `.pdf` document of the tailored resume utilizing `fpdf2` directly in-memory before executing the application upload strategy.
- **DeepSeek-VL2 (Tiny)**: Acts as the "Vision Specialist". Before submitting any application, this agent analyzes screenshots of the browser to ensure no required fields are missed, dropdowns are mapped correctly, and CAPTCHAs are detected.
- **Streamlit Dashboard**: Hosted on port `8501`, providing a clean interface to input the user's compliance profile, view the generated **Master Password**, and monitor the live application logs.

## Setup & Deployment Instructions (RunPod)

ApplyGenie uses GitHub Actions to automatically build and push the Docker image `yanga4/applygenie:latest` to Docker Hub on every push to the `main` branch. 

### Setting Up GitHub Secrets
Before pushing, ensure you have set the following secrets in your GitHub repository (`Settings` > `Secrets and variables` > `Actions`):
- `DOCKER_USERNAME` (Your Docker Hub username: `yanga4`)
- `DOCKER_PASSWORD` (A Docker Hub Access Token)

### Deploying to RunPod
Because the image is hosted on Docker Hub and contains the entire stack, you do **not** need to use the terminal. You can deploy it natively via the RunPod UI!

**1. Create a Custom Template**
- Go to RunPod -> **Templates** -> Click **New Template**.
- **Template Name:** ApplyGenie
- **Container Image:** `yanga4/applygenie:latest`
- **Container Disk:** 40 GB
- **Volume Disk:** 50 GB (To store the 20GB DeepSeek AI models persistently)
- **Expose HTTP Ports:** (Leave blank)
- **Expose TCP Ports:** `8080, 8501, 8000`
- **Environment Variables:**
  - Key: `VNC_PASSWORD` | Value: `your_secure_password` (Optional, defaults to applygenie2026)

Click **Save Template**.

**2. Deploy the Pod**
- Go to **Pods** -> **Deploy**.
- Select a GPU with at least 24GB VRAM (e.g., RTX 3090, RTX 4090).
- Select your new **ApplyGenie** template from the dropdown.
- Click **Deploy**.

**3. Watch it Boot!**
- The first time the pod boots, it will automatically download the DeepSeek models to the persistent `/workspace/ollama` directory. (You can check the pod logs in the RunPod dashboard to watch the download progress).
- Once the logs show the UI has started, click "Connect" and open:
  - **Port 8501** for the Streamlit UI.
  - **Port 8080** for the noVNC live browser view.

## Security: The "Secure Surrogate" Logic

By design, ApplyGenie generates a high-entropy 16-character **Master Password** on its first launch. This password is:
- Displayed in the Streamlit UI.
- Used by the Selenium agent for every new account creation on job portals.
- This ensures you never reuse your personal passwords, isolating job portal credentials completely.

Furthermore, the X11VNC session is protected by the `VNC_PASSWORD` environment variable (default: `applygenie2026`), preventing unauthorized access to the virtual browser.

## Using ApplyGenie

1. Open the Streamlit Dashboard via the exposed port `8501`.
2. Fill out your compliance profile and resume text. Click **Save Profile**.
3. Copy a Target Job URL into the Mission Control panel and click **Launch ApplyGenie**.
4. Monitor the text logs in Streamlit, or click the **Open noVNC Viewer** link to watch the agent physically navigate the browser on port `8080`.
5. **Manual Intervention Loop**: If the agent encounters a 2FA Verification Code (e.g., sent to your email), it will pause and pulse an alert in Streamlit. Paste the code into the Streamlit UI, and the agent will resume the application.
