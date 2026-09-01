# 05 — CI/CD Pipeline (GitHub Actions, $0)

## Why GitHub Actions Is the Right Free Choice Here
You get, on a free public or private repo (2,000 free minutes/month on private repos): a cron scheduler, a CI runner, secrets storage, and artifact storage — covering scheduling, testing, and deployment triggers without a separate paid service.

## Pipeline Overview
```
.github/workflows/
  ci.yml            # runs on every push/PR: lint + test
  daily-agent.yml    # scheduled: runs the job-search agent
  deploy-dashboard.yml  # (optional, often unnecessary — Vercel auto-deploys on push)
```

## 1. Continuous Integration (`ci.yml`)
Runs on every push — catches breakage before it reaches the scheduled job.

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: "pip"

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Lint
        run: |
          pip install ruff
          ruff check .

      - name: Run unit tests
        env:
          DRY_RUN: "true"
        run: pytest -v --tb=short

      - name: Type check
        run: |
          pip install mypy
          mypy agents/ services/ --ignore-missing-imports
```

## 2. Scheduled Agent Run (`daily-agent.yml`)
This replaces a paid cron server entirely.

```yaml
name: Daily Job Search Agent

on:
  schedule:
    - cron: "30 3 * * *"   # 9:00 AM IST daily (03:30 UTC)
  workflow_dispatch: {}      # allows manual trigger from the Actions tab

jobs:
  run-agent:
    runs-on: ubuntu-latest
    timeout-minutes: 20
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: "pip"

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          playwright install --with-deps chromium

      - name: Run agent
        env:
          DATABASE_URL: ${{ secrets.DATABASE_URL }}
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
          GMAIL_CREDENTIALS: ${{ secrets.GMAIL_CREDENTIALS }}
          HUNTER_API_KEY: ${{ secrets.HUNTER_API_KEY }}
          DRY_RUN: "false"
        run: python main.py

      - name: Upload run log on failure
        if: failure()
        uses: actions/upload-artifact@v4
        with:
          name: run-log-${{ github.run_id }}
          path: logs/
```

**Notes:**
- `workflow_dispatch` lets you manually trigger a run from the GitHub UI — invaluable for testing without waiting for the schedule.
- `timeout-minutes: 20` prevents a hung scraping call from burning your free minutes quota indefinitely.
- Cron schedules on GitHub Actions can drift by several minutes under load — acceptable for a daily job, don't rely on it for anything second-precision.

## 3. Dashboard Deployment
If using Vercel for the frontend (doc 03), **don't duplicate this in GitHub Actions** — Vercel's GitHub integration already auto-builds and deploys on every push to `main`, for free, with preview deployments on PRs. Adding a redundant Actions workflow just burns your free minutes for no benefit.

If you deploy the dashboard somewhere without native GitHub integration, a minimal deploy job looks like:
```yaml
name: Deploy Dashboard
on:
  push:
    branches: [main]
    paths: ["dashboard/**"]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Trigger deploy hook
        run: curl -X POST "${{ secrets.DEPLOY_HOOK_URL }}"
```

## Secrets Setup Checklist
In GitHub repo → Settings → Secrets and variables → Actions, add:
- `DATABASE_URL`
- `GEMINI_API_KEY` (and `GROQ_API_KEY` if using fallback)
- `GMAIL_CREDENTIALS` (base64-encoded OAuth token JSON)
- `HUNTER_API_KEY`
- `DEPLOY_HOOK_URL` (if applicable)

## Monitoring the Pipeline (Free)
- GitHub Actions has a built-in **Insights → Actions** usage view showing minutes consumed — check monthly against the free-tier cap (2,000 min/month private repos) so a runaway retry loop doesn't silently exhaust it.
- Add a final step in `daily-agent.yml` that POSTs a one-line summary to a free Discord/Slack webhook (jobs processed, emails sent, errors count) — gives you a daily heartbeat without opening GitHub.
- Failed runs automatically show a red ✗ in the Actions tab and (if enabled in your GitHub notification settings) email you — free built-in alerting, no extra tool needed.

## Branch/Release Discipline
Even solo, keep it simple but real:
- `main` branch is always deployable; the scheduled workflow always runs off `main`.
- Feature work in short-lived branches, merged via PR so `ci.yml` gates every change.
- Tag releases (`v1.0.0`, etc.) when you cross meaningful milestones (e.g., "first week of unattended sends") — costs nothing, gives you rollback points via `git checkout <tag>` if a change misbehaves.

## Total Monthly Cost
$0 — GitHub Actions (free minutes), Supabase (free Postgres), Vercel (free Hobby hosting), Gemini/Groq (free API tiers), Gmail API (free), Hunter.io (free tier, budgeted carefully). The only thing you're truly constrained by is **free-tier quotas**, not money — so the guardrails in docs 01/02/04 (rate limits, daily caps, dedupe) matter more than they would in a paid setup.
