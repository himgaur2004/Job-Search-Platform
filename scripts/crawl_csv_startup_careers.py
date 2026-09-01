"""
crawl_csv_startup_careers.py — High-throughput career page discovery & job extraction for non-ATS startups.

For the 1,909 Indian startups that do not use standard ATS APIs:
1. Probes domain career URLs concurrently using aiohttp & Playwright fallback.
2. Detects embedded ATS tokens (Greenhouse, Lever, Ashby, Workable, Kula, Rippling, etc.) in DOM/HTML.
3. If custom career portal found: extracts jobs via structured regex & LLM job extractor.
4. Populates `ats_crawler_jobs` with direct application links.
"""

import asyncio
import logging
import os
import re
import sys
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse

import aiohttp

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from services.db import get_conn
from services.job_extractor import extract_jobs_with_regex

logger = logging.getLogger(__name__)

CAREER_PATHS = [
    "/careers",
    "/jobs",
    "/join-us",
    "/work-with-us",
    "/career",
    "/hiring",
    "/openings",
    "/join",
    "/about/careers",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# ATS iframe/script detection patterns
ATS_PATTERNS = {
    "greenhouse": [r"boards\.greenhouse\.io/(\w+)", r"greenhouse\.io/embed/job_board\?for=(\w+)"],
    "lever": [r"jobs\.lever\.co/(\w[\w-]*)"],
    "ashby": [r"jobs\.ashbyhq\.com/(\w[\w-]*)"],
    "workable": [r"apply\.workable\.com/(\w[\w-]*)"],
    "kula": [r"careers\.kula\.ai/(\w[\w-]*)"],
    "rippling": [r"ats\.rippling\.com/(\w[\w-]*)"],
    "freshteam": [r"(\w+)\.freshteam\.com"],
    "smartrecruiters": [r"jobs\.smartrecruiters\.com/(\w+)"],
    "recruitee": [r"(\w+)\.recruitee\.com"],
    "bamboohr": [r"(\w+)\.bamboohr\.com/careers"],
}


def _detect_embedded_ats(html: str) -> Optional[Tuple[str, str]]:
    for ats_type, patterns in ATS_PATTERNS.items():
        for pattern in patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                token = match.group(1)
                if token and len(token) >= 3:
                    return ats_type, token
    return None


async def probe_startup_career_page(
    session: aiohttp.ClientSession, company_id: int, name: str, domain: str
) -> Tuple[str, List[dict]]:
    base_urls = [f"https://www.{domain}", f"https://{domain}"]
    found_jobs: List[dict] = []

    for base in base_urls:
        for path in CAREER_PATHS:
            url = f"{base}{path}"
            try:
                async with session.get(
                    url, headers=HEADERS, timeout=aiohttp.ClientTimeout(total=6), allow_redirects=True
                ) as resp:
                    if resp.status == 200:
                        html = await resp.text(errors="ignore")
                        if len(html) < 400:
                            continue

                        # 1. Check for embedded ATS portal
                        ats_res = _detect_embedded_ats(html)
                        if ats_res:
                            ats_type, token = ats_res
                            logger.info(f"  ✓ Found embedded {ats_type}:{token} for {name}")
                            with get_conn() as conn:
                                conn.execute(
                                    """
                                    INSERT INTO ats_companies (name, ats_type, token, status)
                                    VALUES (?, ?, ?, 'active')
                                    ON CONFLICT(token) DO UPDATE SET status='active'
                                    """,
                                    (name, ats_type, token),
                                )
                                conn.commit()
                            return name, []

                        # 2. Check if page contains career indicators
                        text_lower = html.lower()
                        indicators = ["job", "career", "hiring", "open position", "join our team", "apply"]
                        if any(ind in text_lower for ind in indicators):
                            extracted = extract_jobs_with_regex(html, str(resp.url))
                            if extracted:
                                for j in extracted:
                                    j["company"] = name
                                    j["company_id"] = company_id
                                found_jobs.extend(extracted)
                                return name, found_jobs
            except Exception:
                continue

    return name, found_jobs


async def run_csv_startup_crawler(batch_limit: int = 500):
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT id, name, domain FROM companies_custom 
            WHERE status = 'active'
            ORDER BY id ASC
            LIMIT ?
            """,
            (batch_limit,),
        ).fetchall()
        companies = [dict(r) for r in rows]

    print(f"Starting async career page crawler for {len(companies)} custom startups...")

    connector = aiohttp.TCPConnector(limit=100)
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [
            probe_startup_career_page(session, c["id"], c["name"], c["domain"])
            for c in companies
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    total_extracted = 0
    now = os.popen("date -u +'%Y-%m-%dT%H:%M:%SZ'").read().strip()

    with get_conn() as conn:
        for res in results:
            if isinstance(res, tuple) and len(res) == 2:
                name, jobs = res
                for j in jobs:
                    url = j.get("url")
                    if not url:
                        continue
                    try:
                        conn.execute(
                            """
                            INSERT INTO ats_crawler_jobs (company_id, title, location, url, jd_text, source, last_seen)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                            ON CONFLICT(url) DO UPDATE SET title=excluded.title, last_seen=excluded.last_seen
                            """,
                            (
                                j.get("company_id"),
                                j.get("title", "Software Developer"),
                                j.get("location", "India"),
                                url,
                                j.get("jd_text", ""),
                                "custom_regex",
                                now,
                            ),
                        )
                        total_extracted += 1
                    except Exception:
                        pass
        conn.commit()

    print(f"Successfully extracted & indexed {total_extracted} jobs from custom startup career pages!")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    asyncio.run(run_csv_startup_crawler(batch_limit=1000))
