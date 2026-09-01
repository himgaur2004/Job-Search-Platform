from __future__ import annotations

import os
from typing import List
from langgraph.graph import END, StateGraph

from agents.state import AgentState, JobLead
from agents import email_agent, db_agent
from services.job_sources import fetch_jobs_from_all_sources
from services.db import upsert_job


class Service1State(AgentState):
    search_keyword: str
    search_location: str
    search_experience: str
    search_type: str
    target_jobs: List[JobLead]
    apply_results: List[dict]


def discover_jobs(state: Service1State) -> Service1State:
    keyword = state.get("search_keyword", "Software Engineer")
    location = state.get("search_location", "Remote")
    experience = state.get("search_experience", "Any")
    search_type = state.get("search_type", "all")

    print(f"[discover_jobs] Searching all sources for '{keyword}' in '{location}' (Exp: {experience}, Type: {search_type})")
    result = fetch_jobs_from_all_sources(keyword=keyword, location=location, experience=experience, search_type=search_type)

    if result.errors:
        for err in result.errors:
            state["errors"].append(err)

    target_jobs: List[JobLead] = result.jobs
    print(f"[discover_jobs] Found {len(target_jobs)} total jobs across all sources")

    state["target_jobs"] = target_jobs
    state["apply_results"] = []
    return state


def store_discovered_jobs(state: Service1State) -> Service1State:
    """Persist every discovered job into the SQLite database."""
    jobs = state.get("target_jobs", [])
    stored = 0
    for job in jobs:
        try:
            upsert_job(job, match_score=None)
            stored += 1
        except Exception as e:
            state["errors"].append(f"Failed to store job {job.get('company')}: {e}")
    print(f"[store_discovered_jobs] Stored {stored}/{len(jobs)} jobs to DB")
    return state


def process_jobs(state: Service1State) -> Service1State:
    """Summarize discovered jobs per source."""
    jobs = state.get("target_jobs", [])
    source_counts: dict[str, int] = {}
    for job in jobs:
        src = job.get("source", "unknown")
        source_counts[src] = source_counts.get(src, 0) + 1

    state["apply_results"] = [
        {"source": src, "count": cnt, "status": "discovered"}
        for src, cnt in source_counts.items()
    ]
    return state


def build_service1_graph():
    graph = StateGraph(Service1State)
    graph.add_node("discover_jobs", discover_jobs)
    graph.add_node("store_discovered_jobs", store_discovered_jobs)
    graph.add_node("process_jobs", process_jobs)

    graph.set_entry_point("discover_jobs")
    graph.add_edge("discover_jobs", "store_discovered_jobs")
    graph.add_edge("store_discovered_jobs", "process_jobs")
    graph.add_edge("process_jobs", END)

    return graph.compile()
