"""
jd_fetcher.py — On-demand full JD text fetcher for Greenhouse, Lever, Ashby, and SmartRecruiters.

When raw crawler jobs are stored with empty jd_text, this fetcher calls the ATS detail APIs
to retrieve full JD content (HTML/text), cleans it, and updates SQLite DB so experience analysis is 100% accurate.
"""

import asyncio
import logging
import os
import re
import sys
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

import aiohttp
from bs4 import BeautifulSoup

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from services.db import get_conn

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "application/json,text/html",
}


def clean_html_to_text(html: str) -> str:
    if not html:
        return ""
    try:
        soup = BeautifulSoup(html, "lxml")
        return soup.get_text(separator=" ", strip=True)
    except Exception:
        return re.sub(r"<[^>]+>", " ", html)


async def fetch_jd_for_job(session: aiohttp.ClientSession, url: str, source: str) -> Tuple[str, str]:
    """
    Fetch full JD text for a job given its URL and source platform.
    Returns (url, jd_text).
    """
    if not url:
        return url, ""

    parsed = urlparse(url)

    # 1. Greenhouse Jobs
    if "greenhouse.io" in url or "greenhouse" in source or "gh_jid" in url:
        match = re.search(r"greenhouse\.io/([^/]+)/jobs/(\d+)", url)
        if not match:
            match = re.search(r"gh_jid=(\d+)", url)
            if match:
                job_id = match.group(1)
                board_token = parsed.netloc.replace("www.", "").split(".")[0]
                if board_token in ("careers", "job-boards", "boards"):
                    parts = parsed.path.strip("/").split("/")
                    board_token = parts[0] if parts else "company"
            else:
                return url, ""
        else:
            board_token = match.group(1)
            job_id = match.group(2)

        if board_token and job_id:
            api_url = f"https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs/{job_id}"
            try:
                async with session.get(api_url, headers=HEADERS, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        raw_content = data.get("content", "")
                        return url, clean_html_to_text(raw_content)
            except Exception:
                pass

    # 2. Lever Jobs
    elif "lever.co" in url or "lever" in source:
        match = re.search(r"lever\.co/([^/]+)/([a-f0-9-]+)", url)
        if match:
            company_token = match.group(1)
            posting_id = match.group(2)
            api_url = f"https://api.lever.co/v0/postings/{company_token}/{posting_id}?mode=json"
            try:
                async with session.get(api_url, headers=HEADERS, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        description = (data.get("descriptionPlain", "") or "") + " " + (data.get("descriptionBodyPlain", "") or "") + " " + clean_html_to_text(data.get("description", ""))
                        lists = data.get("lists", [])
                        list_text = " ".join((l.get("text", "") or "") + " " + clean_html_to_text(l.get("content", "") or "") for l in lists if isinstance(l, dict))
                        full_jd = (description + " " + list_text).strip()
                        return url, full_jd
            except Exception:
                pass

    # 3. Ashby Jobs
    elif "ashbyhq.com" in url or "ashby" in source:
        match = re.search(r"ashbyhq\.com/([^/]+)/([a-f0-9-]+)", url)
        if match:
            company_token = match.group(1)
            posting_id = match.group(2)
            api_url = f"https://api.ashbyhq.com/posting-api/job-board/{company_token}?includeCompensation=true"
            try:
                async with session.get(api_url, headers=HEADERS, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        postings = data.get("jobs", [])
                        for p in postings:
                            if p.get("id") == posting_id or p.get("jobUrl") == url:
                                raw_desc = p.get("descriptionHtml", "") or p.get("descriptionPlain", "")
                                return url, clean_html_to_text(raw_desc)
            except Exception:
                pass

    # 4. SmartRecruiters Jobs
    elif "smartrecruiters.com" in url or "smartrecruiters" in source:
        match = re.search(r"smartrecruiters\.com/([^/]+)/(\d+)", url)
        if match:
            company_token = match.group(1)
            posting_id = match.group(2)
            api_url = f"https://api.smartrecruiters.com/v1/companies/{company_token}/postings/{posting_id}"
            try:
                async with session.get(api_url, headers=HEADERS, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        sections = data.get("jobAd", {}).get("sections", {})
                        full_text = " ".join(clean_html_to_text(sec.get("text", "")) for sec in sections.values() if isinstance(sec, dict))
                        return url, full_text.strip()
            except Exception:
                pass

    return url, ""


async def batch_fetch_missing_jds(job_list: List[dict], max_concurrent: int = 30) -> List[dict]:
    """
    Given a list of job dicts ({url, source, jd_text, ...}), fetch missing JDs concurrently
    and return the updated list.
    """
    to_fetch = [j for j in job_list if not j.get("jd_text") or len(j.get("jd_text", "").strip()) < 600]
    if not to_fetch:
        return job_list

    logger.info(f"[jd_fetcher] Fetching full JD text on the fly for {len(to_fetch)} jobs...")

    connector = aiohttp.TCPConnector(limit=max_concurrent)
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [fetch_jd_for_job(session, j["url"], j.get("source", "")) for j in to_fetch]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    fetched_map = {}
    for res in results:
        if isinstance(res, tuple) and len(res) == 2:
            url, text = res
            if text:
                fetched_map[url] = text

    # Update job dicts & persist to SQLite DB
    db_updates = []
    for j in job_list:
        url = j.get("url")
        if url in fetched_map:
            j["jd_text"] = fetched_map[url]
            db_updates.append((fetched_map[url], url))

    if db_updates:
        try:
            with get_conn() as conn:
                conn.executemany(
                    "UPDATE ats_crawler_jobs SET jd_text = ? WHERE url = ?",
                    db_updates
                )
                conn.commit()
            logger.info(f"[jd_fetcher] Successfully fetched & saved {len(db_updates)} full JD texts to DB!")
        except Exception as e:
            logger.warning(f"[jd_fetcher] DB update failed: {e}")

    return job_list
