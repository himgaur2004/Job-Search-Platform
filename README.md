# Job Agent MVP

This project implements the instruction set from the five spec documents:
- LangGraph stateful workflow
- free-tier LLM integration abstraction
- duplicate prevention and run logging
- FastAPI read-only dashboard endpoints
- GitHub Actions CI + daily scheduler

## Quick start

```bash
cd "job agent"
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python main.py
```

## Run API

```bash
uvicorn api:app --reload
```

## Notes
- Default mode is `DRY_RUN=true`, so no Gmail send will happen unless you set `DRY_RUN=false`.
- `jobs_input.json` and `resume.txt` are sample inputs for local testing.
- Set `ENABLE_REMOTE_FETCH=true` to ingest jobs from RemoteOK and Remotive free APIs.
- Recruiter lookup now attempts: explicit email -> JD/page extraction -> pattern guess -> optional Hunter lookup for high-match roles.
- Reply classification is processed from `inbox_entries` table rows with `processed=0`, then written to `replies`.
- New endpoint: `GET /api/replies` for dashboard reply view.
- Gmail inbox sync now runs before classification and inserts unseen inbound messages into `inbox_entries`.
- Reply linkage is now thread-aware: sent emails store Gmail `message_id` + `thread_id`, and inbound replies are matched by thread first, then sender fallback.
