from __future__ import annotations

import json
import os
from pathlib import Path
from typing import cast

from agents.state import AgentState, JobLead
from services.job_sources import fetch_jobs_from_enabled_sources


def fetch_today_job_batch() -> list[JobLead]:
    source_result = fetch_jobs_from_enabled_sources()
    external_jobs = source_result.jobs
    for err in source_result.errors:
        print(f"[WARN] {err}")

    jobs_file = os.getenv("JOBS_FILE", "jobs_input.json")
    file_path = Path(jobs_file)
    local_jobs: list[JobLead] = []
    if file_path.exists():
        raw = json.loads(file_path.read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            raise ValueError("jobs_input.json must contain a JSON list.")
        local_jobs = [cast(JobLead, item) for item in raw if isinstance(item, dict)]

    seen_urls: set[str] = set()
    merged: list[JobLead] = []
    for job in [*local_jobs, *external_jobs]:
        url = job.get("url", "")
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        merged.append(job)
    return merged


def run(state: AgentState) -> AgentState:
    if not state["raw_jobs"]:
        state["errors"].append("No jobs available in current state.")
        state["send_status"] = "skipped"
    return state
