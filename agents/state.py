from __future__ import annotations

from typing import List, Optional, TypedDict


class JobLead(TypedDict, total=False):
    company: str
    title: str
    location: str
    url: str
    jd_text: str
    source: str
    recruiter_name: str
    recruiter_email: str


class AgentState(TypedDict):
    raw_jobs: List[JobLead]
    current_job: Optional[JobLead]
    recruiter_name: Optional[str]
    recruiter_email: Optional[str]
    match_score: Optional[float]
    email_subject: Optional[str]
    email_body: Optional[str]
    tech_stack: Optional[str]
    latex_content: Optional[str]
    pdf_path: Optional[str]
    gmail_message_id: Optional[str]
    gmail_thread_id: Optional[str]
    already_sent: bool
    send_status: Optional[str]
    errors: List[str]


def initial_state(job: JobLead) -> AgentState:
    return {
        "raw_jobs": [job],
        "current_job": job,
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
