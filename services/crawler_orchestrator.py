"""
crawler_orchestrator.py — Unified orchestrator for the full crawl pipeline.

Pipeline:
1. ATS API Crawl (Greenhouse, Lever, Ashby, Workable, BambooHR, Workday)
2. Career Page Discovery (probe custom companies for career URLs)
3. Browser Crawl + LLM Extraction (for companies with custom career pages)
4. Cleanup (remove stale jobs, update stats)

Can be run as a single command or scheduled via cron.
"""

import logging
import os
import sqlite3
import sys
import time
from datetime import datetime, timezone

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from services.db import get_conn

logger = logging.getLogger(__name__)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def step1_ats_api_crawl(chunks: int = 5) -> dict:
    """Step 1: Crawl all ATS API companies."""
    logger.info("=" * 60)
    logger.info("[STEP 1] ATS API Crawl")
    logger.info("=" * 60)

    from services.ats_crawler import crawl_all
    import asyncio

    stats = asyncio.run(crawl_all(max_chunks=chunks))
    logger.info(f"[STEP 1] Complete: {stats}")
    return stats


def step2_career_discovery() -> dict:
    """Step 2: Discover career pages for custom companies."""
    logger.info("=" * 60)
    logger.info("[STEP 2] Career Page Discovery")
    logger.info("=" * 60)

    from services.career_discovery import discover_career_pages

    stats = discover_career_pages(batch_size=250, max_workers=15)
    logger.info(f"[STEP 2] Complete: {stats}")
    return stats


def step3_browser_crawl_and_extract(batch_size: int = 30) -> dict:
    """Step 3: Browser crawl + LLM extraction for custom career pages."""
    logger.info("=" * 60)
    logger.info("[STEP 3] Browser Crawl + LLM Extraction")
    logger.info("=" * 60)

    from services.browser_crawler import crawl_active_companies
    from services.job_extractor import extract_jobs_with_llm

    stats = {"pages_crawled": 0, "jobs_extracted": 0, "errors": 0}

    # Crawl career pages
    crawled_pages = crawl_active_companies(batch_size=batch_size)
    stats["pages_crawled"] = len(crawled_pages)

    if not crawled_pages:
        logger.info("[STEP 3] No active career pages to process.")
        return stats

    # Extract jobs from each page using LLM
    now = _utc_now()
    for page in crawled_pages:
        try:
            jobs = extract_jobs_with_llm(
                html=page["html"],
                company_name=page["name"],
                career_url=page["career_url"],
            )

            if jobs:
                with get_conn() as conn:
                    for j in jobs:
                        if not j.get("url"):
                            continue
                        try:
                            conn.execute(
                                """
                                INSERT INTO ats_crawler_jobs 
                                (company_id, title, location, url, jd_text, source, last_seen)
                                VALUES (?, ?, ?, ?, ?, ?, ?)
                                ON CONFLICT(url) DO UPDATE SET
                                    title=excluded.title,
                                    location=excluded.location,
                                    last_seen=excluded.last_seen
                                """,
                                (
                                    None,  # No ats_companies entry for custom
                                    j["title"],
                                    j.get("location", "Unknown"),
                                    j["url"],
                                    j.get("jd_text", ""),
                                    j.get("source", "custom_llm"),
                                    now,
                                ),
                            )
                            stats["jobs_extracted"] += 1
                        except sqlite3.Error as e:
                            logger.debug(f"DB insert error: {e}")

                    # Mark the company as crawled
                    conn.execute(
                        "UPDATE companies_custom SET last_checked=? WHERE id=?",
                        (now, page["company_id"]),
                    )

                logger.info(
                    f"  ✓ {page['name']}: extracted {len(jobs)} jobs"
                )
            else:
                logger.info(f"  ○ {page['name']}: no jobs found")

            # Rate limit between LLM calls (respect Groq free tier: 30 RPM)
            time.sleep(2)

        except Exception as e:
            stats["errors"] += 1
            logger.error(f"  ✗ {page['name']}: {e}")

    logger.info(f"[STEP 3] Complete: {stats}")
    return stats


def step4_cleanup() -> dict:
    """Step 4: Cleanup stale jobs and update stats."""
    logger.info("=" * 60)
    logger.info("[STEP 4] Cleanup")
    logger.info("=" * 60)

    with get_conn() as conn:
        # Delete jobs not seen in 7 days
        deleted = conn.execute(
            "DELETE FROM ats_crawler_jobs WHERE julianday('now') - julianday(last_seen) > 7"
        ).rowcount

        # Get final stats
        total_jobs = conn.execute("SELECT count(*) as c FROM ats_crawler_jobs").fetchone()["c"]
        total_companies = conn.execute("SELECT count(*) as c FROM ats_companies").fetchone()["c"]
        custom_companies = conn.execute("SELECT count(*) as c FROM companies_custom").fetchone()["c"]

        # Source breakdown
        sources = conn.execute(
            "SELECT source, count(*) as c FROM ats_crawler_jobs GROUP BY source ORDER BY c DESC"
        ).fetchall()

    stats = {
        "stale_deleted": deleted or 0,
        "total_jobs": total_jobs,
        "total_ats_companies": total_companies,
        "total_custom_companies": custom_companies,
        "by_source": {r["source"]: r["c"] for r in sources},
    }

    logger.info(f"[STEP 4] Cleanup: deleted {stats['stale_deleted']} stale jobs")
    logger.info(f"[STEP 4] Final stats: {total_jobs} jobs, {total_companies} ATS companies, {custom_companies} custom companies")
    for source, count in stats["by_source"].items():
        logger.info(f"  {source}: {count}")

    # Automatically sync fresh engineering jobs to the main 'jobs' table for Dashboard rendering
    try:
        from scripts.sync_crawler_jobs_to_dashboard import sync_jobs_to_dashboard
        sync_jobs_to_dashboard()
    except Exception as e:
        logger.warning(f"[STEP 4] Sync to dashboard failed: {e}")

    return stats


def run_full_pipeline(ats_chunks: int = 5, browser_batch: int = 30) -> dict:
    """Run the complete crawl pipeline."""
    start = time.time()
    logger.info("*" * 60)
    logger.info("[ORCHESTRATOR] Starting full crawl pipeline")
    logger.info("*" * 60)

    results = {}

    try:
        results["step1_ats"] = step1_ats_api_crawl(chunks=ats_chunks)
    except Exception as e:
        logger.error(f"[STEP 1] Failed: {e}")
        results["step1_ats"] = {"error": str(e)}

    try:
        results["step2_discovery"] = step2_career_discovery()
    except Exception as e:
        logger.error(f"[STEP 2] Failed: {e}")
        results["step2_discovery"] = {"error": str(e)}

    try:
        results["step3_browser"] = step3_browser_crawl_and_extract(batch_size=browser_batch)
    except Exception as e:
        logger.error(f"[STEP 3] Failed: {e}")
        results["step3_browser"] = {"error": str(e)}

    try:
        results["step4_cleanup"] = step4_cleanup()
    except Exception as e:
        logger.error(f"[STEP 4] Failed: {e}")
        results["step4_cleanup"] = {"error": str(e)}

    elapsed = time.time() - start
    logger.info("*" * 60)
    logger.info(f"[ORCHESTRATOR] Pipeline complete in {elapsed:.0f}s")
    logger.info("*" * 60)

    results["elapsed_seconds"] = elapsed
    return results


if __name__ == "__main__":
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    parser = argparse.ArgumentParser(description="Job Discovery Pipeline Orchestrator")
    parser.add_argument("--step", type=int, help="Run only a specific step (1-4)")
    parser.add_argument("--ats-chunks", type=int, default=5, help="Number of ATS crawl chunks")
    parser.add_argument("--browser-batch", type=int, default=30, help="Browser crawl batch size")
    args = parser.parse_args()

    if args.step:
        if args.step == 1:
            step1_ats_api_crawl(chunks=args.ats_chunks)
        elif args.step == 2:
            step2_career_discovery()
        elif args.step == 3:
            step3_browser_crawl_and_extract(batch_size=args.browser_batch)
        elif args.step == 4:
            step4_cleanup()
        else:
            print(f"Invalid step: {args.step}. Must be 1-4.")
    else:
        run_full_pipeline(
            ats_chunks=args.ats_chunks,
            browser_batch=args.browser_batch,
        )
