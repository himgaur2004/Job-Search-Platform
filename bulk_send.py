from __future__ import annotations

import json
import os
from pathlib import Path
from datetime import datetime, timezone
import pandas as pd
from dotenv import load_dotenv

from agents.state import initial_state
from agents import email_agent, db_agent
from services.db import init_db, store_run_log
from services.name_parser import parse_name_from_email

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

def run_bulk(file_path: str):
    load_dotenv()
    init_db()

    print(f"Reading {file_path}...")
    if file_path.endswith('.csv'):
        df = pd.read_csv(file_path)
    elif file_path.endswith('.xlsx'):
        df = pd.read_excel(file_path)
    else:
        raise ValueError("Unsupported file format. Use .csv or .xlsx")

    # Lowercase column names for flexibility
    df.columns = [col.lower().strip() for col in df.columns]
    
    if "email" not in df.columns or "company" not in df.columns:
        raise ValueError("The input file must contain 'email' and 'company' columns.")

    sent_count = 0
    errors: list[str] = []
    run_started = _now()
    daily_cap = int(os.getenv("DAILY_SEND_CAP", "25"))

    for index, row in df.iterrows():
        if sent_count >= daily_cap:
            errors.append("Daily send cap reached; remaining jobs skipped.")
            print("Daily cap reached.")
            break
            
        email = str(row['email']).strip()
        company = str(row['company']).strip()
        if not email or email.lower() == 'nan':
            continue
            
        # Optional title column, defaults to "General Application"
        title = str(row.get('title', 'General Application')).strip()
        if title.lower() == 'nan':
            title = 'General Application'

        recruiter_name = parse_name_from_email(email)
        print(f"Processing: {email} ({company}) -> Extracted Name: {recruiter_name}")

        job_lead = {
            "company": company,
            "title": title,
            "location": "Remote",
            "url": "",
            "jd_text": "BULK", # Special flag to bypass JD check
            "source": "bulk_csv",
            "recruiter_name": recruiter_name,
            "recruiter_email": email
        }
        
        state = initial_state(job_lead)
        # We simulate the graph execution for bulk sending
        state["recruiter_name"] = recruiter_name
        state["recruiter_email"] = email
        state["match_score"] = 1.0 # Force a perfect match for dashboard stats
        
        # 1. Generate Email
        state = email_agent.generate(state)
        if state.get("send_status") == "failed":
            errors.extend(state.get("errors", []))
            continue
            
        # 2. Check Deduplicate
        state = db_agent.check_duplicate(state)
        
        # 3. Send Email
        if not state.get("already_sent"):
            state = email_agent.send(state)
        else:
            print(f"  -> Skipped: Already sent to {email} for {company}")
            
        # 4. Store Result
        state = db_agent.store_result(state)

        if state.get("send_status") == "sent":
            print(f"  -> Successfully sent to {email}")
            sent_count += 1
        elif state.get("errors"):
            errors.extend(state["errors"])

    run_finished = _now()
    store_run_log(
        run_started=run_started,
        run_finished=run_finished,
        jobs_processed=len(df),
        emails_sent=sent_count,
        errors=json.dumps(errors),
    )
    
    print("\n=== Bulk Run Complete ===")
    print(f"Rows processed: {len(df)}")
    print(f"Emails sent: {sent_count}")
    print(f"Errors: {len(errors)}")

if __name__ == "__main__":
    import sys
    
    file_to_run = "bulk_input.csv"
    if len(sys.argv) > 1:
        file_to_run = sys.argv[1]
        
    if not Path(file_to_run).exists():
        print(f"Error: Could not find {file_to_run}")
        print("Please create bulk_input.csv with 'email' and 'company' columns.")
        sys.exit(1)
        
    run_bulk(file_to_run)
