import sqlite3
import os
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

DB_PATH = os.environ.get("APPLYGENIE_DB_PATH", "/app/job_queue.db")

def init_db():
    """Initializes the SQLite database and creates the job_queue table if it doesn't exist."""
    try:
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS job_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT UNIQUE NOT NULL,
                title TEXT,
                company TEXT,
                status TEXT DEFAULT 'PENDING',
                logs TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Ensure 'status' index exists to quickly find 'PENDING' jobs
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_status ON job_queue(status)")
        
        conn.commit()
        logger.info(f"Database initialized at {DB_PATH}")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
    finally:
        if 'conn' in locals():
            conn.close()

def add_job_to_queue(url: str, title: str = "Unknown", company: str = "Unknown") -> bool:
    """
    Adds a new job URL to the queue with status 'PENDING'.
    Returns True if successfully added, False if it was a duplicate or error.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO job_queue (url, title, company, status)
            VALUES (?, ?, ?, 'PENDING')
        ''', (url, title, company))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        # URL already exists in the queue
        return False
    except Exception as e:
        logger.error(f"Error adding job to queue: {e}")
        return False
    finally:
        if 'conn' in locals():
            conn.close()

def get_next_pending_job() -> Optional[Dict]:
    """Fetches the oldest PENDING job from the queue and marks it IN_PROGRESS."""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute(\"SELECT * FROM job_queue WHERE status = 'PENDING' ORDER BY created_at ASC LIMIT 1\")
        job = cursor.fetchone()
        
        if job:
            # Atomic update to prevent multiple workers grabbing the same job
            cursor.execute("UPDATE job_queue SET status = 'IN_PROGRESS', updated_at = CURRENT_TIMESTAMP WHERE id = ?", (job['id'],))
            conn.commit()
            return dict(job)
        return None
    except Exception as e:
        logger.error(f"Error getting next job: {e}")
        return None
    finally:
        if 'conn' in locals():
            conn.close()

def update_job_status(job_id: int, status: str, log_message: str = ""):
    """Updates a job's status (e.g., SUCCESS, FAILED) and appends to its logs."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # We append to existing logs, separated by newlines
        cursor.execute('''
            UPDATE job_queue 
            SET status = ?, 
                logs = COALESCE(logs, '') || CASE WHEN logs IS NULL OR logs = '' THEN '' ELSE '\\n' END || ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (status, log_message, job_id))
        
        conn.commit()
    except Exception as e:
        logger.error(f"Error updating job status: {e}")
    finally:
        if 'conn' in locals():
            conn.close()

def get_all_jobs() -> List[Dict]:
    """Retrieves all jobs for the Streamlit dashboard."""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM job_queue ORDER BY updated_at DESC")
        return [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        logger.error(f"Error fetching all jobs: {e}")
        return []
    finally:
        if 'conn' in locals():
            conn.close()
