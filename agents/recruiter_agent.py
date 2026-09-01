from __future__ import annotations

from agents.state import AgentState
from services.recruiter import discover_recruiter


def run(state: AgentState) -> AgentState:
    job = state.get("current_job")
    if not job:
        state["errors"].append("Missing current_job.")
        state["send_status"] = "failed"
        return state

    result = discover_recruiter(job=job, current_match_score=state.get("match_score"))
    state["recruiter_name"] = result.recruiter_name or "Hiring Team"
    state["recruiter_email"] = result.recruiter_email
    state["errors"].extend(result.errors)
    if not state["recruiter_email"]:
        state["send_status"] = "skipped"
        state["errors"].append("Recruiter email unavailable.")
    return state
