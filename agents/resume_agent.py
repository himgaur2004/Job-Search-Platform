from __future__ import annotations

import os
from pathlib import Path

from agents.state import AgentState
from services.matching import match_score


def _resume_text() -> str:
    resume_file = Path(os.getenv("RESUME_FILE", "resume.txt"))
    if not resume_file.exists():
        raise FileNotFoundError(f"Resume file not found: {resume_file}")
    return resume_file.read_text(encoding="utf-8")


def run(state: AgentState) -> AgentState:
    job = state.get("current_job")
    if not job:
        state["errors"].append("Missing current_job for scoring.")
        state["send_status"] = "failed"
        return state
    jd_text = job.get("jd_text", "")
    state["match_score"] = match_score(_resume_text(), jd_text)
    return state
