"""
discover_ats_tokens.py — Discover and verify company tokens across SmartRecruiters, Recruitee, Breezy HR, Teamtailor, Freshteam, Kula, Ashby, Workable, BambooHR, Workday, and iCIMS.

Mines tokens via web search pattern discovery, verifies public endpoints, and inserts valid tokens into ats_companies.
"""

import asyncio
import logging
import os
import re
import sys
from typing import Dict, List, Set, Tuple

import aiohttp
from ddgs import DDGS

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from services.db import get_conn

logger = logging.getLogger(__name__)

# Search dorks for each ATS platform
ATS_DORKS = [
    ("smartrecruiters", r'jobs\.smartrecruiters\.com/([a-zA-Z0-9_\-]+)', 'site:jobs.smartrecruiters.com "software" OR "engineer" OR "developer"'),
    ("recruitee", r'([a-zA-Z0-9_\-]+)\.recruitee\.com', 'site:recruitee.com "jobs" OR "careers" OR "hiring"'),
    ("breezy", r'([a-zA-Z0-9_\-]+)\.breezy\.hr', 'site:breezy.hr "positions" OR "careers" OR "hiring"'),
    ("teamtailor", r'([a-zA-Z0-9_\-]+)\.teamtailor\.com', 'site:teamtailor.com "jobs" OR "careers"'),
    ("freshteam", r'([a-zA-Z0-9_\-]+)\.freshteam\.com', 'site:freshteam.com "jobs" OR "careers"'),
    ("kula", r'([a-zA-Z0-9_\-]+)\.kula\.ai', 'site:kula.ai "jobs" OR "careers"'),
    ("ashby", r'jobs\.ashbyhq\.com/([a-zA-Z0-9_\-]+)', 'site:jobs.ashbyhq.com "software" OR "engineer"'),
    ("workable", r'apply\.workable\.com/([a-zA-Z0-9_\-]+)', 'site:apply.workable.com "software" OR "engineer"'),
    ("bamboohr", r'([a-zA-Z0-9_\-]+)\.bamboohr\.com', 'site:bamboohr.com/careers "software" OR "engineer"'),
    ("workday", r'([a-zA-Z0-9_\-]+)\.(?:wd1|wd3|wd5|wd12)?\.?myworkdayjobs\.com', 'site:myworkdayjobs.com "software" OR "engineer"'),
    ("icims", r'([a-zA-Z0-9_\-]+)\.icims\.com', 'site:icims.com/jobs "software" OR "engineer"'),
]

IGNORE_TOKENS = {
    "www", "api", "jobs", "careers", "app", "static", "cdn", "help", "support",
    "privacy", "terms", "blog", "about", "contact", "login", "signup", "auth",
    "assets", "media", "docs", "developer", "developers", "portal", "en", "us",
}


def mine_tokens_from_search() -> Dict[str, Set[str]]:
    """Mine candidate tokens for each ATS provider using web search dorks."""
    ddgs = DDGS()
    discovered: Dict[str, Set[str]] = {ats: set() for ats, _, _ in ATS_DORKS}

    for ats, regex, dork in ATS_DORKS:
        logger.info(f"[discover_ats_tokens] Searching dork for {ats}: {dork}")
        try:
            results = list(ddgs.text(dork, max_results=40))
            for r in results:
                url = r.get("href", "")
                snippet = r.get("body", "")
                title = r.get("title", "")
                text_to_search = f"{url} {snippet} {title}"

                matches = re.findall(regex, text_to_search, re.IGNORECASE)
                for match in matches:
                    tok = match.lower().strip()
                    if tok and len(tok) >= 2 and tok not in IGNORE_TOKENS:
                        discovered[ats].add(tok)
        except Exception as e:
            logger.debug(f"Search dork error for {ats}: {e}")

    return discovered


async def verify_token(session: aiohttp.ClientSession, ats: str, token: str) -> Tuple[str, str, bool]:
    """Verify if a candidate ATS token has an active live job board endpoint."""
    endpoints = {
        "smartrecruiters": f"https://api.smartrecruiters.com/v1/companies/{token}/postings",
        "recruitee": f"https://api.recruitee.com/c/{token}/careers/offers",
        "breezy": f"https://{token}.breezy.hr/api/positions",
        "teamtailor": f"https://{token}.teamtailor.com/jobs.json",
        "freshteam": f"https://{token}.freshteam.com/jobs.json",
        "kula": f"https://api.kula.ai/v1/job-board/{token}/jobs",
        "ashby": f"https://api.ashbyhq.com/posting-api/job-board/{token}",
        "workable": f"https://apply.workable.com/api/v3/accounts/{token}/jobs",
        "bamboohr": f"https://{token}.bamboohr.com/careers/list",
        "greenhouse": f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs",
        "lever": f"https://api.lever.co/v0/postings/{token}",
    }

    url = endpoints.get(ats)
    if not url:
        return ats, token, False

    headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
    try:
        if ats in ("workable",):
            async with session.post(url, json={"query": "", "location": []}, headers=headers, timeout=aiohttp.ClientTimeout(total=4)) as resp:
                return ats, token, resp.status == 200
        else:
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=4)) as resp:
                return ats, token, resp.status in (200, 301, 302)
    except Exception:
        return ats, token, False


async def verify_all_discovered(candidate_tokens: Dict[str, Set[str]]) -> List[Tuple[str, str]]:
    """Verify all candidate tokens concurrently."""
    valid_tokens: List[Tuple[str, str]] = []
    connector = aiohttp.TCPConnector(limit=100)

    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = []
        for ats, tokens in candidate_tokens.items():
            for tok in tokens:
                tasks.append(verify_token(session, ats, tok))

        results = await asyncio.gather(*tasks, return_exceptions=True)
        for res in results:
            if isinstance(res, tuple) and len(res) == 3:
                ats, tok, is_valid = res
                if is_valid:
                    valid_tokens.append((ats, tok))

    return valid_tokens


def insert_verified_tokens(valid_tokens: List[Tuple[str, str]]):
    """Insert verified tokens into ats_companies table."""
    inserted = 0
    with get_conn() as conn:
        for ats, token in valid_tokens:
            name = token.replace("-", " ").replace("_", " ").title()
            try:
                conn.execute(
                    """
                    INSERT INTO ats_companies (name, ats_type, token, status)
                    VALUES (?, ?, ?, 'active')
                    ON CONFLICT(token) DO UPDATE SET
                        ats_type=excluded.ats_type,
                        status='active'
                    """,
                    (name, ats, token)
                )
                inserted += 1
            except Exception as e:
                logger.debug(f"DB insert error for {token}: {e}")
        conn.commit()

    logger.info(f"[discover_ats_tokens] Inserted/Updated {inserted} active verified company tokens into DB!")
    print(f"Successfully verified and saved {inserted} new active company tokens into database!")


def main():
    logging.basicConfig(level=logging.INFO)
    logger.info("Starting ATS token discovery and mining...")
    candidates = mine_tokens_from_search()

    total_candidates = sum(len(toks) for toks in candidates.values())
    logger.info(f"Mined {total_candidates} candidate tokens across {len(candidates)} ATS types.")

    valid_tokens = asyncio.run(verify_all_discovered(candidates))
    logger.info(f"Verified {len(valid_tokens)} active live ATS company tokens.")

    insert_verified_tokens(valid_tokens)


if __name__ == "__main__":
    main()
