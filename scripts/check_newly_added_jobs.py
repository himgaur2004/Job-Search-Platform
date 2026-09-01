"""
check_newly_added_jobs.py — Direct inspection of jobs indexed from newly added startup companies.
"""

import logging
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from services.db import get_conn

logger = logging.getLogger(__name__)


def check_new_company_jobs():
    with get_conn() as conn:
        # Get count of total jobs and unique companies in ats_crawler_jobs
        total_jobs = conn.execute("SELECT count(*) FROM ats_crawler_jobs").fetchone()[0]
        unique_companies = conn.execute("SELECT count(DISTINCT company_id) FROM ats_crawler_jobs").fetchone()[0]

        print(f"Total Indexed Jobs in DB: {total_jobs}")
        print(f"Unique Monitored Companies with Indexed Jobs: {unique_companies}")

        # Query recent entry-level software engineering jobs
        query = """
        SELECT title, company_id, location, url, source, last_seen
        FROM ats_crawler_jobs
        WHERE (title LIKE '%Software%' OR title LIKE '%Engineer%' OR title LIKE '%Developer%' OR title LIKE '%Backend%' OR title LIKE '%Frontend%' OR title LIKE '%Full%')
        ORDER BY last_seen DESC
        LIMIT 25
        """
        rows = conn.execute(query).fetchall()

        print(f"\nRecent Entry-Level Engineering Jobs ({len(rows)} shown):")
        for i, (title, comp, loc, url, src, last_seen) in enumerate(rows, 1):
            print(f"{i}. {title} @ {comp} ({src})")
            print(f"   Location: {loc} | Date: {last_seen}")
            print(f"   Apply Link: {url}")
            print("-" * 60)


if __name__ == "__main__":
    check_new_company_jobs()
