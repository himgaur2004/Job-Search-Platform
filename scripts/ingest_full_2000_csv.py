"""
ingest_full_2000_csv.py — High-scale ingestion and multi-ATS auto-discovery of all 2,000 startups from /Users/gauravsingh/startups_master_2000.csv.
"""

import asyncio
import csv
import logging
import os
import sys
from typing import List, Tuple
from urllib.parse import urlparse

import aiohttp

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from services.db import get_conn

logger = logging.getLogger(__name__)

CSV_PATH = "/Users/gauravsingh/startups_master_2000.csv"


def parse_and_seed_custom_companies() -> List[Tuple[str, str, str, str]]:
    if not os.path.exists(CSV_PATH):
        print(f"Error: CSV file not found at {CSV_PATH}")
        return []

    entries = []
    seen_domains = set()

    with open(CSV_PATH, "r", encoding="utf-8", errors="ignore") as f:
        reader = csv.reader(f)
        header = next(reader, None)

        for row in reader:
            if not row or len(row) < 2:
                continue
            name = row[0].strip()
            url = row[1].strip()
            sector = row[2].strip() if len(row) > 2 else "Technology"

            if not url or not name:
                continue

            parsed = urlparse(url if url.startswith("http") else f"https://{url}")
            netloc = parsed.netloc or parsed.path
            domain = netloc.replace("www.", "").split("/")[0].strip().lower()

            if not domain or domain in seen_domains:
                continue
            seen_domains.add(domain)

            career_url = f"https://www.{domain}/careers"
            entries.append((name, domain, career_url, sector))

    print(f"Parsed {len(entries)} unique startup entries from {CSV_PATH}!")

    inserted = 0
    with get_conn() as conn:
        for name, domain, career_url, sector in entries:
            try:
                conn.execute(
                    """
                    INSERT INTO companies_custom (name, domain, career_url, status)
                    VALUES (?, ?, ?, 'active')
                    ON CONFLICT(domain) DO UPDATE SET
                        career_url=excluded.career_url,
                        status='active'
                    """,
                    (name, domain, career_url),
                )
                inserted += 1
            except Exception as e:
                logger.debug(f"DB error for {name}: {e}")
        conn.commit()

    print(f"Successfully ingested {inserted} companies into companies_custom table!")
    return entries


async def verify_ats_endpoint(session: aiohttp.ClientSession, name: str, token: str, ats: str, url: str) -> Tuple[str, str, str, bool]:
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


async def probe_all_ats_tokens(entries: List[Tuple[str, str, str, str]]):
    connector = aiohttp.TCPConnector(limit=150)
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
        ("teamtailor", "https://{t}.teamtailor.com/jobs.json"),
        ("bamboohr", "https://{t}.bamboohr.com/careers/list"),
    ]

    async with aiohttp.ClientSession(connector=connector) as session:
        for name, domain, _, _ in entries:
            parts = domain.split(".")
            clean_tok = parts[0]
            clean_name = name.lower().replace(" ", "").replace(".com", "").replace(".in", "").replace("-", "")

            candidate_tokens = list({clean_tok, clean_name, domain.replace(".", "")})

            for tok in candidate_tokens:
                if not tok or len(tok) < 3:
                    continue
                for ats_name, ep in ats_endpoints:
                    url = ep.format(t=tok)
                    tasks.append(verify_ats_endpoint(session, name, tok, ats_name, url))

        print(f"Launching {len(tasks)} parallel ATS probes across 11 ATS engines...")
        results = await asyncio.gather(*tasks, return_exceptions=True)

    verified = []
    seen = set()
    for res in results:
        if isinstance(res, tuple) and len(res) == 4:
            name, ats, tok, is_valid = res
            if is_valid and (ats, tok) not in seen:
                seen.add((ats, tok))
                verified.append((name, ats, tok))

    print(f"\n⭐ Verified {len(verified)} live active ATS portals for the 2,000 startups!")
    for name, ats, tok in verified[:20]:
        print(f"  • {name} ({tok}) -> {ats}")
    if len(verified) > 20:
        print(f"  ... and {len(verified) - 20} more verified ATS portals!")

    inserted_ats = 0
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
                    (name, ats_type, token),
                )
                inserted_ats += 1
            except Exception as e:
                logger.debug(f"DB insert error: {e}")
        conn.commit()

    print(f"Successfully inserted {inserted_ats} verified ATS company tokens into database!")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    entries = parse_and_seed_custom_companies()
    if entries:
        asyncio.run(probe_all_ats_tokens(entries))
