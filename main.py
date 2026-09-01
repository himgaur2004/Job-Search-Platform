from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from dotenv import load_dotenv

from agents.graph import build_graph
from agents.search_agent import fetch_today_job_batch
from agents.state import initial_state
from services.db import init_db, store_run_log
from services.inbox_sync import sync_inbox_from_gmail
from services.replies import process_inbox_replies


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_daily() -> dict[str, int]:
    load_dotenv()
    init_db()

    jobs = fetch_today_job_batch()
    graph = build_graph()
    sent_count = 0
    errors: list[str] = []
    run_started = _now()

    daily_cap = int(os.getenv("DAILY_SEND_CAP", "25"))
    for job in jobs:
        if sent_count >= daily_cap:
            errors.append("Daily send cap reached; remaining jobs skipped.")
            break
        state = initial_state(job)
        result = graph.invoke(state)
        if result.get("send_status") == "sent":
            sent_count += 1
        if result.get("errors"):
            errors.extend(result["errors"])

    inbox_sync_result = sync_inbox_from_gmail(limit=int(os.getenv("INBOX_SYNC_LIMIT", "50")))
    errors.extend(inbox_sync_result.errors)

    reply_result = process_inbox_replies(limit=int(os.getenv("REPLY_BATCH_LIMIT", "50")))
    errors.extend(reply_result.errors)

    run_finished = _now()
    store_run_log(
        run_started=run_started,
        run_finished=run_finished,
        jobs_processed=len(jobs),
        emails_sent=sent_count,
        errors=json.dumps(errors),
    )
    return {
        "jobs_processed": len(jobs),
        "emails_sent": sent_count,
        "inbox_entries_synced": inbox_sync_result.inserted_entries,
        "replies_processed": reply_result.processed_entries,
    }


if __name__ == "__main__":
    result = run_daily()
    print(json.dumps(result))
