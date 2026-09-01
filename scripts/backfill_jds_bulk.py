"""
backfill_jds_bulk.py — Bulk backfill missing JD text for all ats_crawler_jobs.

Fetches full JD content from Greenhouse, Lever, Ashby, SmartRecruiters APIs
and updates the SQLite database. Run as a background job or schedule daily.

Usage:
    python scripts/backfill_jds_bulk.py [--batch-size 500] [--max-batches 10]
"""

import argparse
import asyncio
import logging
import os
import sys
import time

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from services.db import get_conn
from services.jd_fetcher import batch_fetch_missing_jds

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def get_jobs_missing_jd(batch_size: int = 500, offset: int = 0) -> list[dict]:
    """Get a batch of jobs with empty or very short JD text."""
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT url, source, title, location, jd_text
            FROM ats_crawler_jobs
            WHERE jd_text IS NULL OR length(jd_text) < 100
            ORDER BY last_seen DESC
            LIMIT ? OFFSET ?
            """,
            (batch_size, offset),
        ).fetchall()
        return [dict(r) for r in rows]


def backfill(batch_size: int = 500, max_batches: int = 20):
    """Run the backfill in batches."""
    with get_conn() as conn:
        total_empty = conn.execute(
            "SELECT COUNT(*) as c FROM ats_crawler_jobs WHERE jd_text IS NULL OR length(jd_text) < 100"
        ).fetchone()["c"]

    logger.info(f"Total jobs with empty/short JD: {total_empty:,}")
    logger.info(f"Running {max_batches} batches of {batch_size} jobs each...")

    total_filled = 0
    for batch_num in range(max_batches):
        jobs = get_jobs_missing_jd(batch_size=batch_size, offset=0)
        if not jobs:
            logger.info("No more jobs with missing JDs. Done!")
            break

        logger.info(f"Batch {batch_num + 1}/{max_batches}: Processing {len(jobs)} jobs...")
        t0 = time.time()

        updated = asyncio.run(batch_fetch_missing_jds(jobs, max_concurrent=50))

        filled_this_batch = sum(
            1 for j in updated if j.get("jd_text") and len(j.get("jd_text", "")) >= 100
        )
        total_filled += filled_this_batch
        elapsed = time.time() - t0

        logger.info(
            f"  Batch {batch_num + 1} complete: {filled_this_batch}/{len(jobs)} JDs fetched "
            f"({elapsed:.1f}s, {total_filled:,} total filled)"
        )

        if batch_num < max_batches - 1:
            time.sleep(1)

    with get_conn() as conn:
        remaining_empty = conn.execute(
            "SELECT COUNT(*) as c FROM ats_crawler_jobs WHERE jd_text IS NULL OR length(jd_text) < 100"
        ).fetchone()["c"]

    logger.info(f"\nBackfill complete!")
    logger.info(f"  Total JDs filled: {total_filled:,}")
    logger.info(f"  Remaining empty: {remaining_empty:,}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Bulk backfill missing JD text")
    parser.add_argument("--batch-size", type=int, default=500, help="Jobs per batch")
    parser.add_argument("--max-batches", type=int, default=20, help="Max number of batches")
    args = parser.parse_args()
    backfill(batch_size=args.batch_size, max_batches=args.max_batches)
