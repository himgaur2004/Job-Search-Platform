# 04 — Backend

## Stack (all free tier)
| Component | Choice | Free Tier Detail |
|---|---|---|
| API framework | FastAPI | Open source, no cost |
| Database | Supabase (Postgres) | Free tier: 500MB DB, more than enough here |
| Alternative DB | SQLite (file-based) | Zero setup, fine if you skip the dashboard's need for remote reads |
| ORM | SQLModel or SQLAlchemy | Free, type-safe with FastAPI |
| Resume parsing | `pdfplumber` | Free, pure Python |
| Job scraping | Playwright (headless) | Free; respect robots.txt and ToS per source |
| Recruiter email discovery | Hunter.io free tier (25 searches/mo) + manual LinkedIn fallback | Budget searches carefully; see below |
| Email sending | Gmail API (OAuth) | Free, ~500 sends/day cap on personal Gmail |
| Hosting | Render free web service, or a scheduled GitHub Actions job (no persistent server needed) | See CI/CD doc for the no-server pattern |

**Key decision: do you need a persistent server at all?** If the only "backend" job is (a) run once a day, (b) expose a few read endpoints for the dashboard — you don't need an always-on FastAPI server for (a). Run the agent as a **GitHub Actions scheduled job** (fully free, no cold-start/spin-down issues) and only run FastAPI as a lightweight service for (b), which Render's free tier handles fine (accepting it sleeps after inactivity and cold-starts on the next dashboard visit — acceptable for a personal tool).

## Database Schema
```sql
CREATE TABLE jobs (
    id SERIAL PRIMARY KEY,
    company TEXT NOT NULL,
    title TEXT NOT NULL,
    location TEXT,
    url TEXT UNIQUE NOT NULL,
    jd_text TEXT,
    source TEXT,
    match_score FLOAT,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE recruiters (
    id SERIAL PRIMARY KEY,
    job_id INTEGER REFERENCES jobs(id),
    name TEXT,
    email TEXT,
    UNIQUE(job_id, email)
);

CREATE TABLE emails (
    id SERIAL PRIMARY KEY,
    job_id INTEGER REFERENCES jobs(id),
    recruiter_email TEXT NOT NULL,
    subject TEXT,
    body TEXT,
    status TEXT CHECK (status IN ('sent','skipped','failed')),
    sent_at TIMESTAMPTZ,
    dedupe_key TEXT UNIQUE NOT NULL  -- hash(company + recruiter_email + title)
);

CREATE TABLE replies (
    id SERIAL PRIMARY KEY,
    email_id INTEGER REFERENCES emails(id),
    raw_text TEXT,
    category TEXT,
    confidence FLOAT,
    received_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE run_log (
    id SERIAL PRIMARY KEY,
    run_started TIMESTAMPTZ,
    run_finished TIMESTAMPTZ,
    jobs_processed INT,
    emails_sent INT,
    errors JSONB
);
```
The `dedupe_key UNIQUE` constraint is your real duplicate-prevention mechanism — enforce it at the DB level, not just in application logic, so a race or a bug can't double-send.

## Core Services

**Duplicate check (doc_agent.py):**
```python
import hashlib

def dedupe_key(company: str, recruiter_email: str, title: str) -> str:
    raw = f"{company.lower()}|{recruiter_email.lower()}|{title.lower()}"
    return hashlib.sha256(raw.encode()).hexdigest()

def already_sent(session, key: str) -> bool:
    return session.query(Email).filter_by(dedupe_key=key).first() is not None
```

**Gmail send (services/gmail.py):**
```python
from googleapiclient.discovery import build
from email.mime.text import MIMEText
import base64

def send_email(creds, to: str, subject: str, body: str):
    service = build("gmail", "v1", credentials=creds)
    message = MIMEText(body)
    message["to"] = to
    message["subject"] = subject
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    return service.users().messages().send(userId="me", body={"raw": raw}).execute()
```
Use OAuth2 with a **refresh token stored as a secret**, not a service account with domain-wide delegation (that requires Workspace, not free personal Gmail).

**Recruiter discovery budget:** Hunter.io's free tier is ~25 searches/month — that's roughly 1 search/day, which won't scale to dozens of jobs/day. Practical free approach:
1. Try scraping the recruiter name directly off the job posting or company careers page first (free, no API call).
2. Fall back to a generic pattern-guess (`firstname.lastname@company.com`, common at many companies) + a free email-verification check (many verifiers have a small free tier) before spending a Hunter.io credit.
3. Reserve Hunter.io calls for the highest-match-score jobs only (>85%), where a successful application is worth the scarce quota.

## API Endpoints (for dashboard reads)
```python
# main.py
from fastapi import FastAPI
app = FastAPI()

@app.get("/api/summary")
def summary(db: Session = Depends(get_db)):
    return {
        "sent_today": count_sent_today(db),
        "replies": count_replies(db),
        "interviews": count_by_category(db, "INTERVIEW"),
        "success_rate": success_rate(db),
    }

@app.get("/api/jobs")
def jobs(limit: int = 50, offset: int = 0, db: Session = Depends(get_db)):
    return list_jobs(db, limit, offset)
```
Keep these **read-only**. Don't expose a `/send` endpoint publicly unless it's authenticated and rate-limited — see frontend doc's note on this.

## Secrets Management (Free)
- Local dev: `.env` file, gitignored.
- GitHub Actions: repository **Secrets** (Settings → Secrets and variables → Actions) — free, encrypted at rest.
- Render/Vercel: their built-in environment variable stores — free on Hobby/free tiers.
- Never commit `credentials.json` (Gmail OAuth) or API keys — add to `.gitignore` from commit #1.

## Production Hardening Checklist
- [ ] All external calls wrapped in retry + timeout (see doc 01)
- [ ] `dedupe_key` UNIQUE constraint at DB level
- [ ] Daily send cap enforced in code, not just intention
- [ ] Structured logging to file + `run_log` table
- [ ] `.env`/secrets never committed; verify with `git log -p | grep -i key` before first push
- [ ] DB backups: Supabase free tier includes point-in-time recovery on some plans — otherwise, a weekly `pg_dump` to a GitHub Actions artifact or free storage (e.g., a private GitHub repo) is a zero-cost backup
