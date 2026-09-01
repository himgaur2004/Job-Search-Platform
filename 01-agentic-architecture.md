# 01 — Agentic Code Architecture

## Goal
A LangGraph-based agent that runs daily, searches jobs, finds recruiter contacts, matches your resume, writes a personalized email, dedupes, sends, and logs — with zero hosting cost.

## Why LangGraph over plain LangChain
You have a **cyclical, stateful, conditional workflow** (skip on duplicate, skip on low match score, retry on failure). LangGraph models this as an explicit state graph instead of a linear chain, which is what you actually need here — not because it's trendier.

## Shared State Object
Every node reads/writes a single typed state dict. Define it once so nodes stay decoupled:

```python
# agents/state.py
from typing import TypedDict, Optional, List

class JobLead(TypedDict):
    company: str
    title: str
    location: str
    url: str
    jd_text: str
    source: str

class AgentState(TypedDict):
    raw_jobs: List[JobLead]
    current_job: Optional[JobLead]
    recruiter_name: Optional[str]
    recruiter_email: Optional[str]
    match_score: Optional[float]
    email_subject: Optional[str]
    email_body: Optional[str]
    already_sent: bool
    send_status: Optional[str]
    errors: List[str]
```

Keep state **flat and serializable** — you'll want to persist it to Postgres/SQLite for crash recovery, so avoid objects that don't JSON-serialize cleanly.

## Graph Definition

```python
# agents/graph.py
from langgraph.graph import StateGraph, END
from agents.state import AgentState
from agents import search_agent, recruiter_agent, resume_agent, email_agent, db_agent

def build_graph():
    g = StateGraph(AgentState)

    g.add_node("search_jobs", search_agent.run)
    g.add_node("find_recruiter", recruiter_agent.run)
    g.add_node("match_resume", resume_agent.run)
    g.add_node("generate_email", email_agent.generate)
    g.add_node("check_duplicate", db_agent.check_duplicate)
    g.add_node("send_email", email_agent.send)
    g.add_node("store_result", db_agent.store_result)

    g.set_entry_point("search_jobs")
    g.add_edge("search_jobs", "find_recruiter")
    g.add_edge("find_recruiter", "match_resume")

    # Conditional: skip low-match jobs entirely
    g.add_conditional_edges(
        "match_resume",
        lambda s: "generate_email" if s["match_score"] >= 0.70 else "store_result",
    )
    g.add_edge("generate_email", "check_duplicate")
    g.add_conditional_edges(
        "check_duplicate",
        lambda s: "store_result" if s["already_sent"] else "send_email",
    )
    g.add_edge("send_email", "store_result")
    g.add_edge("store_result", END)

    return g.compile()
```

## Per-Job Loop
LangGraph graphs process one state at a time, so wrap the compiled graph in a driver loop that iterates jobs and **isolates failures per job** (one bad job shouldn't kill the whole run):

```python
# main.py
graph = build_graph()

def run_daily():
    jobs = fetch_today_job_batch()  # from search_agent, batched upstream
    for job in jobs:
        state: AgentState = {
            "raw_jobs": [job], "current_job": job,
            "recruiter_name": None, "recruiter_email": None,
            "match_score": None, "email_subject": None,
            "email_body": None, "already_sent": False,
            "send_status": None, "errors": [],
        }
        try:
            graph.invoke(state)
        except Exception as e:
            log_error(job, e)
            continue  # never let one failure stop the batch
```

## Resilience Patterns (non-negotiable for production, still free)
1. **Idempotency key** — hash `(company, recruiter_email, job_title)` before any send. Check this in DB *before* calling the LLM, not just before Gmail send — saves your (rate-limited) free LLM quota too.
2. **Retry with backoff** on every external call (scraper, email-finder, LLM, Gmail) — use `tenacity` (free, pure Python):
   ```python
   from tenacity import retry, wait_exponential, stop_after_attempt

   @retry(wait=wait_exponential(min=2, max=30), stop=stop_after_attempt(4))
   def call_llm(prompt): ...
   ```
3. **Circuit breaker per source** — if LinkedIn scraping fails 5x in a row, skip that source for the rest of the run rather than retrying into a ban.
4. **Rate limiting** — self-imposed delays (2–5s) between scrape requests and between emails sent (Gmail free tier caps ~500/day on personal accounts — stay well under to avoid flags).
5. **Daily send cap** — hard-code a max (e.g., 20–30/day) regardless of how many matches you find. Protects your Gmail account reputation, which is your only "infrastructure" here.
6. **Dry-run mode** — an env flag (`DRY_RUN=true`) that runs the whole graph but stops before `send_email`, writing to a `pending_review` table instead. Use this for the first week to sanity-check output before trusting it unattended.

## Observability Without Paid Tools
- Structured logging (Python `logging` + JSON formatter) to a local file, rotated with `logging.handlers.RotatingFileHandler` — free, no external service.
- Every node writes its own status + timestamp to a `run_log` table so a failed run is fully diagnosable from the DB alone.
- Optional: push a daily summary to a free Discord/Slack webhook (both free tiers support this) — one HTTP POST, no dependency.

## Folder Structure (agent layer only)
```
agents/
  state.py
  search_agent.py       # scraping + JD extraction
  recruiter_agent.py     # recruiter/email discovery
  resume_agent.py        # embedding similarity scoring
  email_agent.py         # generate() + send()
  db_agent.py            # check_duplicate() + store_result()
  graph.py               # graph wiring
main.py                  # driver loop, invoked by scheduler
```

## What NOT to over-engineer
- Don't reach for a message queue (Celery/Redis) at this scale — a single sequential loop with retries handles tens-to-low-hundreds of jobs/day fine, and keeps you on free compute (a GitHub Actions runner or a free-tier VM).
- Don't add a vector DB (ChromaDB) unless your resume corpus is large enough that plain cosine similarity over a handful of embeddings feels slow — it won't, at this scale. Covered more in doc 02.
