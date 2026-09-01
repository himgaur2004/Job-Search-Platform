"""
probe_user_csv_ats.py — Probe 212 Indian startup domains across 10 ATS engines and seed verified tokens into ats_companies.
"""

import asyncio
import logging
import os
import sys
from typing import List, Tuple

import aiohttp

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from services.db import get_conn

logger = logging.getLogger(__name__)


async def verify_ats(session: aiohttp.ClientSession, name: str, token: str, ats: str, url: str) -> Tuple[str, str, str, bool]:
    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
    try:
        if ats == "workable":
            async with session.post(url, json={"query": "", "location": []}, headers=headers, timeout=aiohttp.ClientTimeout(total=4)) as resp:
                return name, ats, token, resp.status == 200
        else:
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=4)) as resp:
                return name, ats, token, resp.status in (200, 301, 302)
    except Exception:
        return name, ats, token, False


async def probe_all():
    with get_conn() as conn:
        rows = conn.execute("SELECT name, domain FROM companies_custom WHERE status = 'active'").fetchall()

    logger.info(f"Probing {len(rows)} companies across 10 ATS platforms...")

    connector = aiohttp.TCPConnector(limit=100)
    tasks = []

    ats_endpoints = [
        ("greenhouse", "https://boards-api.greenhouse.io/v1/boards/{t}/jobs"),
        ("lever", "https://api.lever.co/v0/postings/{t}"),
        ("ashby", "https://api.ashbyhq.com/posting-api/job-board/{t}"),
        ("workable", "https://apply.workable.com/api/v3/accounts/{t}/jobs"),
        ("breezy", "https://{t}.breezy.hr/api/positions"),
        ("freshteam", "https://{t}.freshteam.com/jobs.json"),
        ("recruitee", "https://api.recruitee.com/c/{t}/careers/offers"),
        ("smartrecruiters", "https://api.smartrecruiters.com/v1/companies/{t}/postings"),
        ("rippling", "https://ats.rippling.com/api/v1/board/{t}/jobs"),
    ]

    async with aiohttp.ClientSession(connector=connector) as session:
        for name, domain in rows:
            clean_tok = domain.replace(".in", "").replace(".co", "").replace(".com", "").replace(".org", "").replace(".io", "")
            tokens = list({clean_tok, domain.split(".")[0], name.lower().replace(" ", "").replace(".com", "").replace(".in", "")})

            for tok in tokens:
                if not tok or len(tok) < 3:
                    continue
                for ats_name, ep in ats_endpoints:
                    url = ep.format(t=tok)
                    tasks.append(verify_ats(session, name, tok, ats_name, url))

        results = await asyncio.gather(*tasks, return_exceptions=True)

    verified = []
    seen = set()
    for res in results:
        if isinstance(res, tuple) and len(res) == 4:
            name, ats, tok, is_valid = res
            if is_valid and (ats, tok) not in seen:
                seen.add((ats, tok))
                verified.append((name, ats, tok))

    print(f"\n⭐ Verified {len(verified)} live active ATS portals for CSV startups!")
    for name, ats, tok in verified:
        print(f"  • {name} ({tok}) -> {ats}")

    inserted = 0
    with get_conn() as conn:
        for name, ats_type, token in verified:
            try:
                conn.execute(
                    """
                    INSERT INTO ats_companies (name, ats_type, token, status)
                    VALUES (?, ?, ?, 'active')
                    ON CONFLICT(token) DO UPDATE SET
                        ats_type=excluded.ats_type,
                        name=excluded.name,
                        status='active'
                    """,
                    (name, ats_type, token)
                )
                inserted += 1
            except Exception as e:
                logger.debug(f"Insert error: {e}")
        conn.commit()

    print(f"Successfully inserted {inserted} verified ATS company tokens into database!")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(probe_all())
