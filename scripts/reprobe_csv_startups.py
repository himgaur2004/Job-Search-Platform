"""
reprobe_csv_startups.py — Smart re-probing of CSV startups that failed initial ATS discovery.

Problem: Original ingest_full_2000_csv.py derived ATS tokens from domains (e.g. 'collegedekho' from 'collegedekho.in').
Many Indian startups use:
  - Different domain suffixes (.com, .co, .io, .tech, .money, .one)
  - Hyphenated or abbreviated tokens
  - Company name != domain slug

This script:
1. Extracts clean company names + domain slugs
2. Generates more candidate tokens (name variations, abbreviations, etc.)
3. Probes all 15 ATS endpoints in parallel
4. Inserts verified portals into ats_companies
5. Immediately crawls verified portals for jobs
"""

import asyncio
import csv
import logging
import os
import re
import sys
from typing import Dict, List, Set, Tuple

import aiohttp

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from services.db import get_conn

logger = logging.getLogger(__name__)

CSV_PATH = "/Users/gauravsingh/startups_master_2000.csv"

ATS_ENDPOINTS = [
    ("greenhouse", "https://boards-api.greenhouse.io/v1/boards/{t}/jobs", "GET"),
    ("lever", "https://api.lever.co/v0/postings/{t}", "GET"),
    ("ashby", "https://api.ashbyhq.com/posting-api/job-board/{t}", "GET"),
    ("workable", "https://apply.workable.com/api/v3/accounts/{t}/jobs", "POST"),
    ("breezy", "https://{t}.breezy.hr/api/positions", "GET"),
    ("freshteam", "https://{t}.freshteam.com/jobs.json", "GET"),
    ("recruitee", "https://api.recruitee.com/c/{t}/careers/offers", "GET"),
    ("smartrecruiters", "https://api.smartrecruiters.com/v1/companies/{t}/postings", "GET"),
    ("rippling", "https://ats.rippling.com/api/v1/board/{t}/jobs", "GET"),
    ("teamtailor", "https://{t}.teamtailor.com/jobs.json", "GET"),
    ("bamboohr", "https://{t}.bamboohr.com/careers/list", "GET"),
    ("kula", "https://api.kula.ai/v1/job-board/{t}/jobs", "GET"),
]


def generate_candidate_tokens(name: str, domain: str) -> List[str]:
    """Generate multiple ATS token candidates from company name and domain."""
    tokens: Set[str] = set()

    # 1. Domain slug (e.g. 'collegedekho' from 'collegedekho.in')
    parts = domain.split(".")
    slug = parts[0].lower()
    if len(slug) >= 3:
        tokens.add(slug)

    # 2. Clean company name variations
    clean_name = re.sub(r"[^a-z0-9]", "", name.lower())
    if len(clean_name) >= 3:
        tokens.add(clean_name)

    # 3. Hyphenated name (e.g. 'college-dekho')
    hyphen_name = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    if len(hyphen_name) >= 3 and hyphen_name != clean_name:
        tokens.add(hyphen_name)

    # 4. Words-joined (no space) (e.g. 'collegedekho')
    words = re.findall(r"[a-z0-9]+", name.lower())
    if len(words) > 1:
        joined = "".join(words)
        if len(joined) >= 3:
            tokens.add(joined)
        # Also try first word only (many startups use just first word)
        if len(words[0]) >= 3:
            tokens.add(words[0])

    # 5. Common suffixes removed (e.g. 'curefit' from 'Curefit Technologies')
    for suffix in ["technologies", "labs", "tech", "ai", "io", "india", "inc", "pvt", "ltd", "private", "limited", "solutions"]:
        cleaned = clean_name.replace(suffix, "")
        if len(cleaned) >= 3 and cleaned != clean_name:
            tokens.add(cleaned)

    # 6. Full domain without TLD extensions
    full_domain = domain.replace(".", "")
    if len(full_domain) >= 3:
        tokens.add(full_domain)

    return list(tokens)


async def probe_single(
    session: aiohttp.ClientSession, name: str, token: str, ats_name: str, url: str, method: str
) -> Tuple[str, str, str, bool, int]:
    """Probe a single ATS endpoint. Returns (name, ats, token, valid, job_count)."""
    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)", "Accept": "application/json"}
    try:
        if method == "POST":
            async with session.post(url, json={"query": "", "location": []}, headers=headers,
                                     timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    results = data.get("results", [])
                    return name, ats_name, token, len(results) > 0, len(results)
        else:
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    # Check if response actually has jobs
                    if isinstance(data, list):
                        return name, ats_name, token, len(data) > 0, len(data)
                    elif isinstance(data, dict):
                        jobs = data.get("jobs", data.get("content", data.get("offers", data.get("result", data.get("data", [])))))
                        if isinstance(jobs, list) and len(jobs) > 0:
                            return name, ats_name, token, True, len(jobs)
                        # For Lever-style response (array of postings)
                        job_postings = data.get("jobPostings", [])
                        if isinstance(job_postings, list) and len(job_postings) > 0:
                            return name, ats_name, token, True, len(job_postings)
    except Exception:
        pass
    return name, ats_name, token, False, 0


async def reprobe_unmatched_startups():
    """Re-probe all CSV startups that have NO active ATS portal."""
    # 1. Load CSV startups
    entries = []
    with open(CSV_PATH, "r", encoding="utf-8", errors="ignore") as f:
        reader = csv.reader(f)
        next(reader, None)  # skip header
        for row in reader:
            if not row or len(row) < 2:
                continue
            name = row[0].strip()
            url = row[1].strip()
            if name and url:
                from urllib.parse import urlparse
                parsed = urlparse(url if url.startswith("http") else f"https://{url}")
                netloc = parsed.netloc or parsed.path
                domain = netloc.replace("www.", "").split("/")[0].strip().lower()
                if domain:
                    entries.append((name, domain))

    print(f"Loaded {len(entries)} CSV startups")

    # 2. Find which ones already have active ATS portals
    with get_conn() as conn:
        existing_tokens = set()
        rows = conn.execute("SELECT token FROM ats_companies WHERE status = 'active'").fetchall()
        for r in rows:
            existing_tokens.add(r["token"].lower())

    # 3. Filter to unmatched only
    unmatched = []
    for name, domain in entries:
        candidate_tokens = generate_candidate_tokens(name, domain)
        if not any(tok in existing_tokens for tok in candidate_tokens):
            unmatched.append((name, domain))

    print(f"Unmatched startups (no active ATS portal): {len(unmatched)}")

    # 4. Probe all unmatched startups
    tasks = []
    connector = aiohttp.TCPConnector(limit=200)
    async with aiohttp.ClientSession(connector=connector) as session:
        for name, domain in unmatched:
            candidate_tokens = generate_candidate_tokens(name, domain)
            for tok in candidate_tokens:
                for ats_name, ep_template, method in ATS_ENDPOINTS:
                    url = ep_template.format(t=tok)
                    tasks.append(probe_single(session, name, tok, ats_name, url, method))

        print(f"Launching {len(tasks)} parallel ATS probes...")
        results = await asyncio.gather(*tasks, return_exceptions=True)

    # 5. Collect verified portals (with jobs)
    verified = []
    seen = set()
    for res in results:
        if isinstance(res, tuple) and len(res) == 5:
            name, ats, tok, is_valid, job_count = res
            if is_valid and job_count > 0 and (ats, tok) not in seen:
                seen.add((ats, tok))
                verified.append((name, ats, tok, job_count))

    print(f"\n⭐ Verified {len(verified)} NEW live ATS portals with active jobs!")
    for name, ats, tok, jc in verified[:30]:
        print(f"  • {name} -> {ats}:{tok} ({jc} jobs)")
    if len(verified) > 30:
        print(f"  ... and {len(verified) - 30} more!")

    # 6. Insert into ats_companies
    inserted = 0
    with get_conn() as conn:
        for name, ats_type, token, _ in verified:
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
                inserted += 1
            except Exception as e:
                logger.debug(f"DB insert error: {e}")
        conn.commit()

    print(f"\nInserted {inserted} new verified ATS portals into database!")

    # 7. Now crawl these new companies immediately
    if verified:
        print(f"\n=== Immediately crawling {len(verified)} newly verified companies... ===")
        from services.ats_crawler import ATS_FETCHERS, REQUEST_TIMEOUT
        from datetime import datetime, timezone

        total_jobs = 0
        now = datetime.now(timezone.utc).isoformat()

        async with aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(limit=30),
            timeout=REQUEST_TIMEOUT
        ) as session:
            with get_conn() as db_conn:
                for name, ats_type, token, _ in verified:
                    fetcher = ATS_FETCHERS.get(ats_type)
                    if not fetcher:
                        continue
                    try:
                        # The crawler fetchers expect (session, token) for async, 
                        # but ats_aggregator fetchers expect (comp_dict, keyword, location).
                        # Use ats_crawler fetchers directly
                        jobs = await fetcher(session, token)
                        
                        # Look up company_id
                        ac_row = db_conn.execute(
                            "SELECT id FROM ats_companies WHERE token = ? AND ats_type = ?",
                            (token, ats_type)
                        ).fetchone()
                        cid = ac_row["id"] if ac_row else None
                        
                        for j in jobs:
                            if not j.get("url"):
                                continue
                            try:
                                db_conn.execute(
                                    """INSERT INTO ats_crawler_jobs (company_id, title, location, url, jd_text, source, last_seen)
                                    VALUES (?, ?, ?, ?, ?, ?, ?)
                                    ON CONFLICT(url) DO UPDATE SET title=excluded.title, location=excluded.location, last_seen=excluded.last_seen""",
                                    (cid, j.get("title", ""), j.get("location", "Unknown"), j["url"], j.get("jd_text", ""), j.get("source", f"ats_{ats_type}"), now)
                                )
                                total_jobs += 1
                            except Exception:
                                pass
                        
                        if cid:
                            db_conn.execute("UPDATE ats_companies SET last_scraped = ? WHERE id = ?", (now, cid))
                        db_conn.commit()
                        
                    except Exception as e:
                        logger.debug(f"Crawl error for {name}/{ats_type}/{token}: {e}")

        print(f"\n=== DONE: Crawled {total_jobs} jobs from {len(verified)} newly discovered ATS portals ===")

    return len(verified), inserted


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    asyncio.run(reprobe_unmatched_startups())
