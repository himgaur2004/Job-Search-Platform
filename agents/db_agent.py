from __future__ import annotations

from agents.state import AgentState
from services.db import already_sent, make_dedupe_key, store_email_result, upsert_job


def _dedupe_from_state(state: AgentState) -> str:
    job = state.get("current_job")
    if not job:
        raise ValueError("Missing current_job")
    recruiter_email = state.get("recruiter_email") or "unknown@example.com"
    return make_dedupe_key(job.get("company", ""), recruiter_email, job.get("title", ""))


def check_duplicate(state: AgentState) -> AgentState:
    key = _dedupe_from_state(state)
    state["already_sent"] = already_sent(key)
    return state


def store_result(state: AgentState) -> AgentState:
    job = state.get("current_job")
    if not job:
        state["errors"].append("Missing current_job for store_result.")
        state["send_status"] = "failed"
        return state
    job_id = upsert_job(job, state.get("match_score"))
    
    import os
    match_score = state.get("match_score")
    is_high_match = match_score is not None and match_score >= float(os.getenv("MATCH_THRESHOLD", "0.70"))
    
    recruiter_email = state.get("recruiter_email")
    if not recruiter_email:
        if is_high_match:
            recruiter_email = f"needs_email_{job_id}@manual.review"
        else:
            recruiter_email = "unknown@example.com"
            
    # Regenerate dedupe key with potentially new placeholder email
    key = make_dedupe_key(job.get("company", ""), recruiter_email, job.get("title", ""))
    
    status = "skipped" if state.get("already_sent") else (state.get("send_status") or "failed")
    store_email_result(
        job_id=job_id,
        recruiter_email=recruiter_email,
        subject=state.get("email_subject"),
        body=state.get("email_body"),
        status=status,
        dedupe_key=key,
        gmail_message_id=state.get("gmail_message_id"),
        gmail_thread_id=state.get("gmail_thread_id"),
    )
    
    # Clear the stage now that the job is completely finished processing
    from services.db import update_job_stage
    update_job_stage(job_id, None)
    
    return state
