"""
verify_ats_companies.py — Verify all 13,500+ ATS companies in ats_companies database.

Sends fast async HTTP HEAD/GET requests to validate if the ATS token is alive.
Updates status column in ats_companies table:
  - status = 'active'   (returns 200 OK with valid board)
  - status = 'invalid'  (returns 404 Not Found, DNS error, or 403)
"""

import asyncio
import logging
import os
import sqlite3
import sys
import time

import aiohttp

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from services.db import get_conn, init_db

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

CONCURRENCY = 100
TIMEOUT = aiohttp.ClientTimeout(total=8)


async def check_greenhouse(session: aiohttp.ClientSession, token: str) -> bool:
    url = f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs"
    try:
        async with session.get(url) as resp:
            return resp.status == 200
    except Exception:
        return False


async def check_lever(session: aiohttp.ClientSession, token: str) -> bool:
    url = f"https://api.lever.co/v0/postings/{token}?mode=json"
    try:
        async with session.get(url) as resp:
            return resp.status == 200
    except Exception:
        return False


async def check_ashby(session: aiohttp.ClientSession, token: str) -> bool:
    url = f"https://api.ashbyhq.com/posting-api/job-board/{token}"
    try:
        async with session.get(url) as resp:
            return resp.status == 200
    except Exception:
        return False


async def check_workable(session: aiohttp.ClientSession, token: str) -> bool:
    url = f"https://apply.workable.com/api/v3/accounts/{token}/jobs"
    try:
        async with session.post(url, json={"query": "", "location": []}) as resp:
            return resp.status == 200
    except Exception:
        return False


async def check_bamboohr(session: aiohttp.ClientSession, token: str) -> bool:
    url = f"https://{token}.bamboohr.com/careers/list"
    try:
        async with session.get(url, headers={"Accept": "application/json"}) as resp:
            return resp.status == 200
    except Exception:
        return False


async def check_workday(session: aiohttp.ClientSession, token: str) -> bool:
    url = f"https://{token}.wd1.myworkdayjobs.com/wday/cxs/{token}/External/jobs"
    try:
        async with session.post(url, json={"limit": 1}) as resp:
            return resp.status in (200, 400)
    except Exception:
        return False


CHECKERS = {
    "greenhouse": check_greenhouse,
    "lever": check_lever,
    "ashby": check_ashby,
    "workable": check_workable,
    "bamboohr": check_bamboohr,
    "workday": check_workday,
}


async def verify_company(
    session: aiohttp.ClientSession, company: dict, sem: asyncio.Semaphore
) -> tuple[int, bool]:
    cid = company["id"]
    token = company["token"]
    ats_type = company["ats_type"]

    checker = CHECKERS.get(ats_type)
    if not checker:
        return cid, False

    async with sem:
        is_valid = await checker(session, token)
        return cid, is_valid


async def run_verification(batch_size: int = 5000):
    init_db()

    # Ensure status column exists in ats_companies
    with get_conn() as conn:
        try:
            conn.execute("ALTER TABLE ats_companies ADD COLUMN status TEXT DEFAULT 'pending'")
        except sqlite3.OperationalError:
            pass

    with get_conn() as conn:
        companies = conn.execute(
            "SELECT id, name, ats_type, token FROM ats_companies WHERE status IS NULL OR status = 'pending' LIMIT ?",
            (batch_size,),
        ).fetchall()
        companies = [dict(c) for c in companies]

    if not companies:
        logger.info("[verify] All ATS companies have been verified.")
        return

    logger.info(f"[verify] Verifying {len(companies)} ATS tokens with concurrency={CONCURRENCY}...")

    sem = asyncio.Semaphore(CONCURRENCY)
    connector = aiohttp.TCPConnector(limit=CONCURRENCY)

    active_ids = []
    invalid_ids = []

    start = time.time()
    async with aiohttp.ClientSession(connector=connector, timeout=TIMEOUT) as session:
        tasks = [verify_company(session, c, sem) for c in companies]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for res in results:
            if isinstance(res, tuple):
                cid, is_valid = res
                if is_valid:
                    active_ids.append(cid)
                else:
                    invalid_ids.append(cid)

    elapsed = time.time() - start
    logger.info(
        f"[verify] Complete in {elapsed:.1f}s: {len(active_ids)} active, {len(invalid_ids)} invalid"
    )

    # Bulk update DB
    with get_conn() as conn:
        if active_ids:
            conn.executemany(
                "UPDATE ats_companies SET status='active' WHERE id=?",
                [(i,) for i in active_ids],
            )
        if invalid_ids:
            conn.executemany(
                "UPDATE ats_companies SET status='invalid' WHERE id=?",
                [(i,) for i in invalid_ids],
            )
        conn.commit()

    # Summary
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT status, count(*) as c FROM ats_companies GROUP BY status"
        ).fetchall()
        print("\n=== ATS COMPANY STATUS SUMMARY ===")
        for r in rows:
            print(f"  {r['status']:10s} {r['c']:>6d}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", type=int, default=5000, help="Batch size to verify")
    args = parser.parse_args()

    asyncio.run(run_verification(batch_size=args.batch))
