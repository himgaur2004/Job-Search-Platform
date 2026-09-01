ou s"""
backfill_jds.py — One-time bulk backfill of missing JD text for all candidate jobs in ats_crawler_jobs.

Fetches full JDs from Greenhouse, Lever, Ashby, and SmartRecruiters detail APIs
for all non-senior software engineering India jobs that currently have empty jd_text.
"""

import asyncio
import logging
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from services.db import get_conn
from services.jd_fetcher import batch_fetch_missing_jds

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)     


TECH_TITLE_INCLUSIONS = [
    "software", "developer", "sde", "frontend", "front-end", "backend", "back-end",
    "fullstack", "full-stack", "full stack", "data engineer", "machine learning",
    "ml engineer", "ai engineer", "devops", "cloud engineer", "qa engineer",
    "automation engineer", "systems engineer", "site reliability", "sre", "web developer",
    "python developer", "java developer", "react developer", "node developer",
    "golang developer", "sdet", "test engineer"
]

SENIOR_EXCLUSIONS = [
    "senior", "sr.", "sr ", "staff", "lead", "principal", "principle", "manager", "director",
    "head", "vp", "vice president", "president", "avp", "evp", "svp", "founding", "chief",
    "architect", "expert", "distinguished", "lead engineer", "senior engineer",
    "senior developer", "tech lead", "team lead"
]

INDIAN_LOCATIONS = [
    "bengaluru", "bangalore", "noida", "gurugram", "gurgaon", "mumbai", "pune",
    "hyderabad", "chennai", "delhi", "kolkata", "ahmedabad", "jaipur", "lucknow",
    "kochi", "thiruvananthapuram", "indore", "chandigarh", "coimbatore", "india",
    "ncr", "greater delhi", "nagpur", "bhubaneswar"
]


def backfill():
    with get_conn() as conn:
        # Get all crawler jobs with empty/truncated JD text (< 600 chars)
        rows = conn.execute("""
            SELECT id, company_id, title, location, url, jd_text, source 
            FROM ats_crawler_jobs 
            WHERE (jd_text IS NULL OR length(jd_text) < 600)
        """).fetchall()

    all_rows = [dict(r) for r in rows]
    logger.info(f"Total jobs with empty/short JD text: {len(all_rows)}")

    # Filter to tech + India candidates only (to avoid wasting API calls)
    candidates = []
    for r in all_rows:
        t = r["title"].lower()
        loc = (r["location"] or "").lower()

        is_tech = any(inc in t for inc in TECH_TITLE_INCLUSIONS)
        if not is_tech:
            continue

        is_senior = any(ex in t for ex in SENIOR_EXCLUSIONS)
        if is_senior:
            continue

        is_india = any(ind in loc for ind in INDIAN_LOCATIONS)
        if not is_india:
            continue

        candidates.append(r)

    logger.info(f"Non-senior tech India candidates to backfill: {len(candidates)}")

    if not candidates:
        logger.info("No candidates to backfill!")
        return

    # Process in batches of 200
    batch_size = 200
    total_fetched = 0

    for i in range(0, len(candidates), batch_size):
        batch = candidates[i:i + batch_size]
        logger.info(f"Processing batch {i // batch_size + 1} ({len(batch)} jobs)...")
        updated = asyncio.run(batch_fetch_missing_jds(batch, max_concurrent=50))

        fetched_in_batch = sum(1 for j in updated if j.get("jd_text") and len(j["jd_text"].strip()) >= 50)
        total_fetched += fetched_in_batch
        logger.info(f"  Fetched {fetched_in_batch} JDs in this batch")

    logger.info(f"\nBackfill complete! Fetched {total_fetched} full JD texts total.")

    # Report final stats
    with get_conn() as conn:
        total = conn.execute("""
            SELECT COUNT(*) FROM ats_crawler_jobs 
            WHERE (lower(title) LIKE '%software%' OR lower(title) LIKE '%developer%' OR lower(title) LIKE '%sde%'
                OR lower(title) LIKE '%engineer%' OR lower(title) LIKE '%frontend%' OR lower(title) LIKE '%backend%')
            AND (lower(location) LIKE '%india%' OR lower(location) LIKE '%bengaluru%' 
                OR lower(location) LIKE '%bangalore%' OR lower(location) LIKE '%pune%'
                OR lower(location) LIKE '%hyderabad%' OR lower(location) LIKE '%mumbai%'
                OR lower(location) LIKE '%chennai%' OR lower(location) LIKE '%delhi%'
                OR lower(location) LIKE '%noida%' OR lower(location) LIKE '%gurugram%')
            AND lower(title) NOT LIKE '%senior%' AND lower(title) NOT LIKE '%sr.%'
            AND lower(title) NOT LIKE '%staff%' AND lower(title) NOT LIKE '%lead%'
            AND lower(title) NOT LIKE '%principal%' AND lower(title) NOT LIKE '%manager%'
            AND lower(title) NOT LIKE '%director%' AND lower(title) NOT LIKE '%head%'
            AND lower(title) NOT LIKE '%architect%'
        """).fetchone()[0]

        with_jd = conn.execute("""
            SELECT COUNT(*) FROM ats_crawler_jobs 
            WHERE (lower(title) LIKE '%software%' OR lower(title) LIKE '%developer%' OR lower(title) LIKE '%sde%'
                OR lower(title) LIKE '%engineer%' OR lower(title) LIKE '%frontend%' OR lower(title) LIKE '%backend%')
            AND (lower(location) LIKE '%india%' OR lower(location) LIKE '%bengaluru%' 
                OR lower(location) LIKE '%bangalore%' OR lower(location) LIKE '%pune%'
                OR lower(location) LIKE '%hyderabad%' OR lower(location) LIKE '%mumbai%'
                OR lower(location) LIKE '%chennai%' OR lower(location) LIKE '%delhi%'
                OR lower(location) LIKE '%noida%' OR lower(location) LIKE '%gurugram%')
            AND lower(title) NOT LIKE '%senior%' AND lower(title) NOT LIKE '%sr.%'
            AND lower(title) NOT LIKE '%staff%' AND lower(title) NOT LIKE '%lead%'
            AND lower(title) NOT LIKE '%principal%' AND lower(title) NOT LIKE '%manager%'
            AND lower(title) NOT LIKE '%director%' AND lower(title) NOT LIKE '%head%'
            AND lower(title) NOT LIKE '%architect%'
            AND jd_text IS NOT NULL AND length(jd_text) >= 50
        """).fetchone()[0]

    logger.info(f"\nFinal Stats:")
    logger.info(f"  Total non-senior SW India jobs: {total}")
    logger.info(f"  With JD text (filterable):      {with_jd}")
    logger.info(f"  Without JD text:                {total - with_jd}")


if __name__ == "__main__":
    backfill()
