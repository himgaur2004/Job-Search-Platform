from __future__ import annotations
import shutil
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv

env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path, override=True)

# Global scout status – survives page navigation
_scout_lock = threading.Lock()
_scout_status = {
    "running": False,
    "started_at": None,
    "finished_at": None,
    "jobs_found": 0,
    "current_keyword": None,
    "error": None,
}

_crawler_lock = threading.Lock()
_crawler_status = {
    "running": False,
    "started_at": None,
    "finished_at": None,
    "last_result": None,
    "error": None,
}


from fastapi import FastAPI, Query, File, UploadFile, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import sqlite3

app = FastAPI(title="Job Agent API", version="0.1.0")

def _background_crawler_worker():
    """Runs the full crawler orchestrator pipeline in background."""
    global _crawler_status
    with _crawler_lock:
        if _crawler_status["running"]:
            return
        _crawler_status["running"] = True
        _crawler_status["started_at"] = datetime.now(timezone.utc).isoformat()
        _crawler_status["error"] = None

    try:
        from services.crawler_orchestrator import run_full_pipeline
        result = run_full_pipeline(ats_chunks=3, browser_batch=15)
        with _crawler_lock:
            _crawler_status["last_result"] = result
    except Exception as e:
        with _crawler_lock:
            _crawler_status["error"] = str(e)
    finally:
        with _crawler_lock:
            _crawler_status["running"] = False
            _crawler_status["finished_at"] = datetime.now(timezone.utc).isoformat()

def _periodic_crawler_loop():
    import time
    while True:
        # Run every 6 hours
        time.sleep(21600)
        try:
            with _crawler_lock:
                is_running = _crawler_status["running"]
            if not is_running:
                print("[Scheduler] Triggering periodic 6-hour crawler orchestrator pipeline...")
                _background_crawler_worker()
        except Exception as e:
            print(f"[Scheduler] Periodic crawler error: {e}")

@app.on_event("startup")
def startup_event():
    import threading
    t = threading.Thread(target=_periodic_crawler_loop, daemon=True)
    t.start()
    init_db()

from services.db import (
    count_by_category, count_replies, count_sent_today, init_db, 
    list_jobs, list_replies, success_rate, list_followups,
    get_setting, set_setting, list_settings,
    list_resumes, get_active_resume, insert_resume, update_resume, delete_resume,
    list_templates, get_active_template, insert_template, update_template, delete_template
)
from bulk_send import run_bulk
from pydantic import BaseModel
from typing import Any
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Job Agent API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.get("/api/summary")
def summary() -> dict[str, float | int]:
    return {
        "sent_today": count_sent_today(),
        "replies": count_replies(),
        "interviews": count_by_category("INTERVIEW"),
        "success_rate": success_rate(),
    }


@app.get("/api/jobs")
def get_jobs(
    limit: int = 100,
    offset: int = 0,
    q: str | None = None,
    location: str | None = None,
    source: str | None = None,
):
    return list_jobs(limit=limit, offset=offset, q=q, location=location, source=source)

@app.delete("/api/jobs")
def delete_all_jobs():
    from services.db import get_conn
    with get_conn() as conn:
        conn.execute("DELETE FROM jobs")
    return {"message": "All jobs deleted"}

class ResumeJobRequest(BaseModel):
    email: str

@app.post("/api/jobs/{job_id}/resume")
def resume_job(job_id: int, payload: ResumeJobRequest, background_tasks: BackgroundTasks):
    from services.db import get_job
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    def run_resume_background(job_data: dict, email: str):
        from agents.resume_job_agent import build_resume_graph
        graph = build_resume_graph()
        state = {
            "current_job": job_data,
            "recruiter_email": email,
            "match_score": job_data.get("match_score"),
            "email_subject": None,
            "email_body": None,
            "tech_stack": None,
            "latex_content": None,
            "pdf_path": None,
            "gmail_message_id": None,
            "gmail_thread_id": None,
            "already_sent": False,
            "send_status": None,
            "errors": [],
        }
        graph.invoke(state)

    background_tasks.add_task(run_resume_background, job, payload.email)
    return {"message": "Job workflow resumed in the background."}

@app.get("/api/replies")
def replies(limit: int = Query(default=50, ge=1, le=200), offset: int = Query(default=0, ge=0)):
    return list_replies(limit=limit, offset=offset)


@app.get("/api/followups")
def followups(limit: int = Query(default=50, ge=1, le=200), offset: int = Query(default=0, ge=0)):
    return list_followups(limit=limit, offset=offset)


@app.post("/api/bulk-send")
def bulk_send(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    temp_path = Path(f"temp_{file.filename}")
    with temp_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    # Run bulk script in background
    background_tasks.add_task(run_bulk, str(temp_path))
    return {"message": "Bulk send started in background."}


class TargetedOutreachRequest(BaseModel):
    emails: list[str]

def run_service2_background(emails: list[str]):
    from agents.service2_agent import build_service2_graph
    graph = build_service2_graph()
    for email in emails:
        # Initialize state with minimal fields required by AgentState
        state = {
            "target_email": email,
            "raw_jobs": [],
            "current_job": None,
            "recruiter_name": None,
            "recruiter_email": None,
            "match_score": None,
            "email_subject": None,
            "email_body": None,
            "tech_stack": None,
            "latex_content": None,
            "pdf_path": None,
            "gmail_message_id": None,
            "gmail_thread_id": None,
            "already_sent": False,
            "send_status": None,
            "errors": [],
        }
        graph.invoke(state)

@app.post("/api/service2/run")
def run_service2(payload: TargetedOutreachRequest, background_tasks: BackgroundTasks):
    background_tasks.add_task(run_service2_background, payload.emails)
    return {"message": f"Targeted outreach started for {len(payload.emails)} emails."}

class AutoHuntRequest(BaseModel):
    keyword: str
    location: str
    experience: str = "Any"
    search_type: str = "all"

def run_service1_background(keyword: str, location: str, experience: str = "Any", search_type: str = "all"):
    global _scout_status

    with _scout_lock:
        _scout_status["running"] = True
        _scout_status["started_at"] = datetime.now(timezone.utc).isoformat()
        _scout_status["finished_at"] = None
        _scout_status["error"] = None
        _scout_status["jobs_found"] = 0
        _scout_status["current_keyword"] = keyword

    try:
        from agents.service1_agent import build_service1_graph
        graph = build_service1_graph()

        # Search exact keyword(s) and location as requested by user
        keywords = [k.strip() for k in keyword.split(",") if k.strip()]
        locations = [location]

        if search_type == "ats":
            combinations = [(kw, loc, "ats") for kw in keywords for loc in locations]
        elif search_type == "all":
            combinations = [(kw, loc, "job_boards") for kw in keywords for loc in locations]
            combinations.extend([(kw, loc, "ats") for kw in keywords for loc in locations])
        else:
            combinations = [(kw, loc, search_type) for kw in keywords for loc in locations]

        total_found = 0
        for kw, loc, stype in combinations:
            with _scout_lock:
                _scout_status["current_keyword"] = f"{kw} in {loc} ({stype})"
            state = {
                "search_keyword": kw,
                "search_location": loc,
                "search_experience": experience,
                "search_type": stype,
                "target_jobs": [],
                "apply_results": [],
                "raw_jobs": [],
                "current_job": None,
                "recruiter_name": None,
                "recruiter_email": None,
                "match_score": None,
                "email_subject": None,
                "email_body": None,
                "tech_stack": None,
                "latex_content": None,
                "pdf_path": None,
                "gmail_message_id": None,
                "gmail_thread_id": None,
                "already_sent": False,
                "send_status": None,
                "errors": [],
            }
            result = graph.invoke(state)
            found = len(result.get("target_jobs", []))
            total_found += found
            with _scout_lock:
                _scout_status["jobs_found"] = total_found
    except Exception as e:
        with _scout_lock:
            _scout_status["error"] = str(e)
    finally:
        with _scout_lock:
            _scout_status["running"] = False
            _scout_status["finished_at"] = datetime.now(timezone.utc).isoformat()
            _scout_status["current_keyword"] = None

@app.get("/api/service1/status")
def get_scout_status():
    with _scout_lock:
        return dict(_scout_status)

@app.post("/api/service1/run")
def run_service1(payload: AutoHuntRequest, background_tasks: BackgroundTasks):
    with _scout_lock:
        if _scout_status["running"]:
            return {"message": "Scout is already running.", "status": "already_running"}
    background_tasks.add_task(run_service1_background, payload.keyword, payload.location, payload.experience, payload.search_type)
    return {"message": f"Scout started for {payload.keyword} in {payload.location} (Exp: {payload.experience}, Type: {payload.search_type}).", "status": "started"}

# --- Crawler Pipeline API ---

@app.get("/api/crawler/stats")
def get_crawler_stats():
    """Return live metrics on indexed companies and jobs across ATS & custom sources."""
    from services.db import get_conn
    with get_conn() as conn:
        total_jobs = conn.execute("SELECT count(*) as c FROM ats_crawler_jobs").fetchone()["c"]
        total_companies = conn.execute("SELECT count(*) as c FROM ats_companies").fetchone()["c"]
        custom_companies = conn.execute("SELECT count(*) as c FROM companies_custom").fetchone()["c"]
        custom_active = conn.execute("SELECT count(*) as c FROM companies_custom WHERE status = 'active'").fetchone()["c"]
        
        sources = conn.execute("SELECT source, count(*) as c FROM ats_crawler_jobs GROUP BY source ORDER BY c DESC").fetchall()
        ats_types = conn.execute("SELECT ats_type, count(*) as c FROM ats_companies GROUP BY ats_type ORDER BY c DESC").fetchall()
        
        india_jobs = conn.execute("""
            SELECT count(*) as c FROM ats_crawler_jobs j 
            WHERE lower(j.location) LIKE '%india%' OR lower(j.location) LIKE '%bengaluru%' OR lower(j.location) LIKE '%bangalore%' 
               OR lower(j.location) LIKE '%pune%' OR lower(j.location) LIKE '%hyderabad%' OR lower(j.location) LIKE '%mumbai%'
               OR lower(j.location) LIKE '%delhi%' OR lower(j.location) LIKE '%noida%' OR lower(j.location) LIKE '%gurugram%'
        """).fetchone()["c"]
        
    return {
        "total_jobs": total_jobs,
        "total_ats_companies": total_companies,
        "total_custom_companies": custom_companies,
        "custom_active_career_pages": custom_active,
        "india_jobs": india_jobs,
        "by_source": {r["source"]: r["c"] for r in sources},
        "by_ats": {r["ats_type"]: r["c"] for r in ats_types},
    }

@app.get("/api/crawler/status")
def get_crawler_status():
    with _crawler_lock:
        return dict(_crawler_status)

@app.post("/api/crawler/run")
def trigger_crawler(background_tasks: BackgroundTasks):
    with _crawler_lock:
        if _crawler_status["running"]:
            return {"message": "Crawler pipeline is already running.", "status": "already_running"}
    background_tasks.add_task(_background_crawler_worker)
    return {"message": "Full crawler orchestrator pipeline started in background.", "status": "started"}

# --- Settings API ---

class SettingUpdate(BaseModel):
    value: str

@app.get("/api/settings")
def get_settings():
    return list_settings()

@app.put("/api/settings/{key}")
def update_setting(key: str, payload: SettingUpdate):
    set_setting(key, payload.value)
    return {"message": f"Setting {key} updated successfully."}


# --- Resumes API ---

class ResumeCreate(BaseModel):
    name: str
    latex_content: str
    is_active: bool = False

class ResumeUpdate(BaseModel):
    name: str
    latex_content: str
    is_active: bool

@app.get("/api/resumes")
def get_resumes():
    return list_resumes()

@app.post("/api/resumes")
def create_resume(payload: ResumeCreate):
    resume_id = insert_resume(payload.name, payload.latex_content, payload.is_active)
    return {"message": "Resume created successfully.", "id": resume_id}

@app.put("/api/resumes/{resume_id}")
def edit_resume(resume_id: int, payload: ResumeUpdate):
    update_resume(resume_id, payload.name, payload.latex_content, payload.is_active)
    return {"message": "Resume updated successfully."}

@app.delete("/api/resumes/{resume_id}")
def remove_resume(resume_id: int):
    delete_resume(resume_id)
    return {"message": "Resume deleted successfully."}


# --- Templates API ---

class TemplateCreate(BaseModel):
    name: str
    subject_template: str
    body_template: str
    is_active: bool = False

class TemplateUpdate(BaseModel):
    name: str
    subject_template: str
    body_template: str
    is_active: bool

@app.get("/api/templates")
def get_templates():
    return list_templates()

@app.post("/api/templates")
def create_template(payload: TemplateCreate):
    template_id = insert_template(payload.name, payload.subject_template, payload.body_template, payload.is_active)
    return {"message": "Template created successfully.", "id": template_id}

@app.put("/api/templates/{template_id}")
def edit_template(template_id: int, payload: TemplateUpdate):
    update_template(template_id, payload.name, payload.subject_template, payload.body_template, payload.is_active)
    return {"message": "Template updated successfully."}

@app.delete("/api/templates/{template_id}")
def remove_template(template_id: int):
    delete_template(template_id)
    return {"message": "Template deleted successfully."}


# --- Auto-Apply API ---

from services.apply_bot import apply_to_job
from pydantic import BaseModel
from fastapi import BackgroundTasks
import time
import random

class ApplyRequest(BaseModel):
    job_id: int
    url: str
    resume_mode: str = "prebuilt"  # "prebuilt" | "generate"

def _run_auto_apply_background(job_id: int, url: str, resume_mode: str = "prebuilt"):
    try:
        from services.db import get_conn

        # Mark as applying
        with get_conn() as conn:
            conn.execute("UPDATE jobs SET status = 'applying' WHERE id = ?", (job_id,))

        # Fetch jd_text from DB for tailored resume generation
        jd_text = ""
        with get_conn() as conn:
            row = conn.execute("SELECT jd_text FROM jobs WHERE id = ?", (job_id,)).fetchone()
            if row and row["jd_text"]:
                jd_text = row["jd_text"]

        print(f"Starting auto-apply for job {job_id}: {url} (mode={resume_mode})")
        result = apply_to_job(url, resume_mode=resume_mode, jd_text=jd_text)
        print(f"Auto-apply result for {job_id}: {result}")

        # Update status — auto-apply is tracked on the jobs table only.
        # The emails table is reserved for recruiter outreach (has NOT NULL recruiter_email).
        status = 'applied' if result.get('success') else 'failed'
        error = result.get('error', '')

        with get_conn() as conn:
            conn.execute(
                "UPDATE jobs SET status = ?, apply_error = ? WHERE id = ?",
                (status, error, job_id)
            )

    except Exception as e:
        print(f"Auto-apply background error: {e}")
        try:
            with get_conn() as conn:
                conn.execute(
                    "UPDATE jobs SET status = 'failed', apply_error = ? WHERE id = ?",
                    (str(e), job_id)
                )
        except Exception:
            pass

@app.post("/api/jobs/{job_id}/apply")
def auto_apply_single(job_id: int, payload: ApplyRequest, background_tasks: BackgroundTasks):
    background_tasks.add_task(
        _run_auto_apply_background, job_id, payload.url, payload.resume_mode
    )
    return {"message": f"Auto-apply queued for job {job_id} (mode={payload.resume_mode})."}

class BatchApplyRequest(BaseModel):
    job_ids: list[int]
    resume_mode: str = "prebuilt"  # "prebuilt" | "generate"

def _run_batch_apply_background(job_ids: list[int], resume_mode: str = "prebuilt"):
    from services.db import get_conn
    for job_id in job_ids:
        with get_conn() as conn:
            row = conn.execute("SELECT url FROM jobs WHERE id = ?", (job_id,)).fetchone()
            if not row or not row["url"]:
                continue
            url = row["url"]
        
        _run_auto_apply_background(job_id, url, resume_mode)
        time.sleep(random.uniform(5, 10))

@app.post("/api/apply/batch")
def auto_apply_batch(payload: BatchApplyRequest, background_tasks: BackgroundTasks):
    background_tasks.add_task(_run_batch_apply_background, payload.job_ids, payload.resume_mode)
    return {"message": f"Batch auto-apply queued for {len(payload.job_ids)} jobs (mode={payload.resume_mode})."}
