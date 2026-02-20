from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import os
import logging
import threading

# Import agentic workflow (to be implemented)
# from app.core.agentic_workflow import run_job_application

app = FastAPI(title="ApplyGenie API", description="Webhook orchestrator for autonomous job applications")

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

class JobApplicationRequest(BaseModel):
    user_id: str
    target_company: str
    job_url: str
    resume_path: str | None = None

@app.get("/")
def read_root():
    return {"status": "ApplyGenie API is running. Access via Streamlit on port 8501."}

@app.post("/api/v1/apply")
def trigger_application(request: JobApplicationRequest):
    """
    Endpoint to trigger a new job application flow programmatically.
    """
    try:
        # In a real system, you'd queue this via Celery/Redis.
        # For now, we'll kick it off in a background thread or let Streamlit handle it.
        logger.info(f"Received application request for {request.target_company}")
        
        # Example of starting the agent in the background:
        # thread = threading.Thread(target=run_job_application, args=(request,))
        # thread.start()
        
        return {"status": "Application process triggered", "job_url": request.job_url}
    
    except Exception as e:
        logger.error(f"Error triggering application: {e}")
        raise HTTPException(status_code=500, detail=str(e))
