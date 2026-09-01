"""
ats_crawler.py — Background crawler that polls ATS APIs for all supported providers.

Supported:
  - Greenhouse (JSON API)
  - Lever (JSON API)
  - Ashby (JSON API)
  - Workable (JSON API)
  - BambooHR (JSON API)
  - Workday (JSON API — multi-cluster discovery)
  - iCIMS (Search API)
  - Oracle HCM (REST API — multi-region discovery)
  - SAP SuccessFactors (Career Site API)

Runs in chunks of CHUNK_SIZE companies per invocation.
Designed to be called repeatedly (e.g. via cron or scheduler).
"""

import asyncio
import json
import logging
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List
import sys
import os

import aiohttp

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from services.db import get_conn

logger = logging.getLogger(__name__)

# ─── Configuration ────────────────────────────────────────────────────────────

CONCURRENCY = 30
CHUNK_SIZE = 500
REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=12)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ─── ATS Fetchers ─────────────────────────────────────────────────────────────

async def fetch_greenhouse(session: aiohttp.ClientSession, token: str) -> List[Dict[str, Any]]:
    url = f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs"
    try:
        async with session.get(url) as resp:
            if resp.status == 200:
                data = await resp.json()
                return [
                    {
                        "title": j.get("title", ""),
                        "location": j.get("location", {}).get("name", "Unknown"),
                        "url": j.get("absolute_url", ""),
                        "jd_text": "",
                        "source": "ats_greenhouse",
                    }
                    for j in data.get("jobs", [])
                ]
    except Exception:
        pass
    return []


async def fetch_lever(session: aiohttp.ClientSession, token: str) -> List[Dict[str, Any]]:
    url = f"https://api.lever.co/v0/postings/{token}?mode=json"
    try:
        async with session.get(url) as resp:
            if resp.status == 200:
                data = await resp.json()
                if not isinstance(data, list):
                    return []
                return [
                    {
                        "title": j.get("text", ""),
                        "location": j.get("categories", {}).get("location", "Unknown"),
                        "url": j.get("hostedUrl", ""),
                        "jd_text": j.get("descriptionPlain", "")[:500],
                        "source": "ats_lever",
                    }
                    for j in data
                ]
    except Exception:
        pass
    return []


async def fetch_ashby(session: aiohttp.ClientSession, token: str) -> List[Dict[str, Any]]:
    url = f"https://api.ashbyhq.com/posting-api/job-board/{token}"
    try:
        async with session.get(url) as resp:
            if resp.status == 200:
                data = await resp.json()
                return [
                    {
                        "title": j.get("title", ""),
                        "location": j.get("location", "Unknown"),
                        "url": j.get("jobUrl", ""),
                        "jd_text": "",
                        "source": "ats_ashby",
                    }
                    for j in data.get("jobs", [])
                ]
    except Exception:
        pass
    return []


async def fetch_workable(session: aiohttp.ClientSession, token: str) -> List[Dict[str, Any]]:
    url = f"https://apply.workable.com/api/v3/accounts/{token}/jobs"
    payload = {"query": "", "location": [], "remote": True}
    try:
        async with session.post(url, json=payload) as resp:
            if resp.status == 200:
                data = await resp.json()
                jobs = []
                for j in data.get("results", []):
                    shortcode = j.get("shortcode", "")
                    loc = j.get("location", {})
                    loc_str = loc.get("location_str", "") if isinstance(loc, dict) else str(loc)
                    jobs.append({
                        "title": j.get("title", ""),
                        "location": loc_str or "Unknown",
                        "url": f"https://apply.workable.com/{token}/j/{shortcode}/" if shortcode else "",
                        "jd_text": "",
                        "source": "ats_workable",
                    })
                return jobs
    except Exception:
        pass
    return []


async def fetch_bamboohr(session: aiohttp.ClientSession, token: str) -> List[Dict[str, Any]]:
    url = f"https://{token}.bamboohr.com/careers/list"
    try:
        async with session.get(url, headers={"Accept": "application/json"}) as resp:
            if resp.status == 200:
                data = await resp.json()
                jobs = []
                for j in data.get("result", []):
                    dept_id = j.get("id", "")
                    loc_info = j.get("location", {})
                    city = loc_info.get("city", "") if isinstance(loc_info, dict) else ""
                    jobs.append({
                        "title": j.get("jobOpeningName", ""),
                        "location": city or "Unknown",
                        "url": f"https://{token}.bamboohr.com/careers/{dept_id}" if dept_id else "",
                        "jd_text": "",
                        "source": "ats_bamboohr",
                    })
                return jobs
    except Exception:
        pass
    return []


async def fetch_workday(session: aiohttp.ClientSession, token: str) -> List[Dict[str, Any]]:
    """Try multiple Workday clusters and sites to find the right endpoint."""
    clusters = ["wd1", "wd3", "wd5"]
    sites = ["External", "CX_1", "Careers", "CorporateCareers", token]
    payload = {"appliedFacets": {}, "limit": 20, "offset": 0, "searchText": ""}

    for cluster in clusters:
        domain = f"{token}.{cluster}.myworkdayjobs.com"
        for site in sites:
            url = f"https://{domain}/wday/cxs/{token}/{site}/jobs"
            try:
                async with session.post(url, json=payload) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        postings = data.get("jobPostings", [])
                        if postings:
                            return [
                                {
                                    "title": j.get("title", ""),
                                    "location": j.get("locationsText", "Unknown"),
                                    "url": f"https://{domain}{j.get('externalPath', '')}",
                                    "jd_text": "",
                                    "source": "ats_workday",
                                }
                                for j in postings
                                if j.get("externalPath")
                            ]
            except Exception:
                pass
    return []


# ─── Startup ATS Fetchers ───────────────────────────────────────────────────

async def fetch_recruitee(session: aiohttp.ClientSession, token: str) -> List[Dict[str, Any]]:
    url = f"https://api.recruitee.com/c/{token}/careers/offers"
    try:
        async with session.get(url) as resp:
            if resp.status == 200:
                data = await resp.json()
                return [
                    {
                        "title": j.get("title", ""),
                        "location": j.get("location") or "Unknown",
                        "url": j.get("careers_url", ""),
                        "jd_text": j.get("description", "")[:300],
                        "source": "ats_recruitee",
                    }
                    for j in data.get("offers", [])
                    if j.get("careers_url")
                ]
    except Exception:
        pass
    return []


async def fetch_smartrecruiters(session: aiohttp.ClientSession, token: str) -> List[Dict[str, Any]]:
    url = f"https://api.smartrecruiters.com/v1/companies/{token}/postings"
    try:
        async with session.get(url) as resp:
            if resp.status == 200:
                data = await resp.json()
                jobs = []
                for j in data.get("content", []):
                    job_id = j.get("id", "")
                    if job_id:
                        loc_info = j.get("location", {})
                        city = loc_info.get("city", "") if isinstance(loc_info, dict) else ""
                        jobs.append({
                            "title": j.get("name", ""),
                            "location": city or "Unknown",
                            "url": f"https://jobs.smartrecruiters.com/{token}/{job_id}",
                            "jd_text": "",
                            "source": "ats_smartrecruiters",
                        })
                return jobs
    except Exception:
        pass
    return []


async def fetch_breezy(session: aiohttp.ClientSession, token: str) -> List[Dict[str, Any]]:
    url = f"https://{token}.breezy.hr/api/positions"
    try:
        async with session.get(url) as resp:
            if resp.status == 200:
                data = await resp.json()
                if isinstance(data, list):
                    return [
                        {
                            "title": j.get("name", ""),
                            "location": j.get("location", {}).get("name", "Unknown") if isinstance(j.get("location"), dict) else "Unknown",
                            "url": f"https://{token}.breezy.hr/p/{j.get('friendly_id')}",
                            "jd_text": "",
                            "source": "ats_breezy",
                        }
                        for j in data
                        if j.get("friendly_id")
                    ]
    except Exception:
        pass
    return []


async def fetch_teamtailor(session: aiohttp.ClientSession, token: str) -> List[Dict[str, Any]]:
    url = f"https://{token}.teamtailor.com/jobs.json"
    try:
        async with session.get(url) as resp:
            if resp.status == 200:
                data = await resp.json()
                jobs = []
                for j in data.get("data", []):
                    attrs = j.get("attributes", {})
                    link = attrs.get("careersite-job-url", "")
                    if link:
                        jobs.append({
                            "title": attrs.get("title", ""),
                            "location": attrs.get("location-name", "Unknown"),
                            "url": link,
                            "jd_text": "",
                            "source": "ats_teamtailor",
                        })
                return jobs
    except Exception:
        pass
    return []


async def fetch_freshteam(session: aiohttp.ClientSession, token: str) -> List[Dict[str, Any]]:
    url = f"https://{token}.freshteam.com/jobs.json"
    try:
        async with session.get(url) as resp:
            if resp.status == 200:
                data = await resp.json()
                if isinstance(data, list):
                    return [
                        {
                            "title": j.get("title", ""),
                            "location": j.get("location") or "Unknown",
                            "url": f"https://{token}.freshteam.com/jobs/{j.get('id')}",
                            "jd_text": "",
                            "source": "ats_freshteam",
                        }
                        for j in data
                        if j.get("id")
                    ]
    except Exception:
        pass
    return []


async def fetch_kula(session: aiohttp.ClientSession, token: str) -> List[Dict[str, Any]]:
    url = f"https://api.kula.ai/v1/job-board/{token}/jobs"
    try:
        async with session.get(url) as resp:
            if resp.status == 200:
                data = await resp.json()
                return [
                    {
                        "title": j.get("title", ""),
                        "location": j.get("location") or "Unknown",
                        "url": j.get("applyUrl") or f"https://{token}.kula.ai/jobs/{j.get('id')}",
                        "jd_text": "",
                        "source": "ats_kula",
                    }
                    for j in data.get("jobs", [])
                    if j.get("id") or j.get("applyUrl")
                ]
    except Exception:
        pass
    return []


async def fetch_rippling(session: aiohttp.ClientSession, token: str) -> List[Dict[str, Any]]:
    url = f"https://ats.rippling.com/api/v1/board/{token}/jobs"
    try:
        async with session.get(url) as resp:
            if resp.status == 200:
                data = await resp.json()
                if isinstance(data, list):
                    return [
                        {
                            "title": j.get("name", ""),
                            "location": j.get("workLocation", {}).get("label", "Unknown") if isinstance(j.get("workLocation"), dict) else "Unknown",
                            "url": j.get("url") or f"https://ats.rippling.com/{token}/jobs/{j.get('uuid')}",
                            "jd_text": "",
                            "source": "ats_rippling",
                        }
                        for j in data
                        if j.get("uuid") or j.get("url")
                    ]
    except Exception:
        pass
    return []


# ─── iCIMS ────────────────────────────────────────────────────────────────────

async def fetch_icims(session: aiohttp.ClientSession, token: str) -> List[Dict[str, Any]]:
    """Fetch jobs from iCIMS Search API.
    Token format: customer ID (numeric), e.g. '12345'
    """
    search_url = f"https://api.icims.com/customers/{token}/search/jobs"
    try:
        async with session.get(search_url) as resp:
            if resp.status != 200:
                return []
            data = await resp.json()
            jobs = []
            for j in data.get("searchResults", []):
                title = j.get("jobtitle", "") or j.get("title", "")
                loc_info = j.get("joblocation", {})
                loc = loc_info.get("value", "") if isinstance(loc_info, dict) else str(loc_info) if loc_info else "Unknown"
                job_id = j.get("id", "")
                if not job_id:
                    continue
                link = f"https://careers.icims.com/jobs/{token}/{job_id}/job"
                jobs.append({
                    "title": title,
                    "location": loc or "Unknown",
                    "url": link,
                    "jd_text": "",
                    "source": "ats_icims",
                })
            return jobs
    except Exception:
        pass
    return []


# ─── Oracle HCM ──────────────────────────────────────────────────────────────

async def fetch_oracle(session: aiohttp.ClientSession, token: str) -> List[Dict[str, Any]]:
    """Fetch jobs from Oracle HCM Cloud REST API.
    Token format: company subdomain, e.g. 'erpkc' for erpkc.oraclecloud.com
    """
    sites = ["CX_1", "CX", "External", "Careers", "CorporateCareers"]
    domain = f"{token}.fa.{{}}.oraclecloud.com"
    regions = ["em2", "em3", "us2", "us6", "ap1", "ap2"]

    for region in regions:
        d = domain.format(region)
        for site in sites:
            url = (
                f"https://{d}/hcmRestApi/resources/latest/recruitingCEJobRequisitions"
                f"?onlyData=true&expand=requisitionList&finder=findReqs;siteNumber={site},limit=200"
            )
            try:
                async with session.get(url) as resp:
                    if resp.status != 200:
                        continue
                    data = await resp.json()
                    items = data.get("items", [])
                    if not items:
                        continue
                    req_list = items[0].get("requisitionList", []) if items else []
                    if not req_list:
                        continue
                    return [
                        {
                            "title": j.get("Title", ""),
                            "location": j.get("PrimaryLocation", "Unknown"),
                            "url": f"https://{d}/hcmUI/CandidateExperience/en/sites/{site}/job/{j.get('Id')}",
                            "jd_text": "",
                            "source": "ats_oracle",
                        }
                        for j in req_list
                        if j.get("Id")
                    ]
            except Exception:
                continue
    return []


# ─── SAP SuccessFactors ──────────────────────────────────────────────────────

async def fetch_successfactors(session: aiohttp.ClientSession, token: str) -> List[Dict[str, Any]]:
    """Fetch jobs from SAP SuccessFactors Career Site Builder API.
    Token format: 'company_instance/site_id', e.g. 'infosys/careers' or just the API host slug.
    """
    # Try common SuccessFactors endpoint patterns
    base_urls = [
        f"https://career{token}.successfactors.com/career?company={token}",
        f"https://career2.successfactors.eu/career?company={token}",
        f"https://career5.successfactors.eu/career?company={token}",
    ]

    # SuccessFactors OData job requisition API
    odata_urls = [
        f"https://api{i}.successfactors.com/odata/v2/JobRequisition?$format=json&$top=200&$select=jobReqId,jobTitle,location,externalJobDescription"
        for i in ["", "2", "4", "5"]
    ]

    # Try the public career site JSON endpoint
    json_urls = [
        f"https://career{suffix}.successfactors.{tld}/career?company={token}&career_ns=job_listing&navBarLevel=JOB_SEARCH&_s.crb=true"
        for suffix in ["", "2", "5"]
        for tld in ["com", "eu"]
    ]

    # Use the simpler career site scrape approach
    career_api = f"https://career{token[0] if token[0].isdigit() else ''}.successfactors.com/career?company={token}&career_ns=job_listing_summary"
    try:
        async with session.get(career_api) as resp:
            if resp.status == 200:
                text = await resp.text()
                # Try JSON parse
                try:
                    data = json.loads(text)
                    jobs = []
                    for j in data.get("JobRequisition", data.get("jobRequisitions", data.get("d", {}).get("results", []))):
                        title = j.get("jobTitle", j.get("title", ""))
                        loc = j.get("location", j.get("primaryLocation", "Unknown"))
                        jid = j.get("jobReqId", j.get("id", ""))
                        if title and jid:
                            jobs.append({
                                "title": title,
                                "location": loc if loc else "Unknown",
                                "url": f"https://career.successfactors.com/career?company={token}&career_job_req_id={jid}",
                                "jd_text": "",
                                "source": "ats_successfactors",
                            })
                    if jobs:
                        return jobs
                except (json.JSONDecodeError, ValueError):
                    pass
    except Exception:
        pass

    return []


# ─── Dispatcher ───────────────────────────────────────────────────────────────

ATS_FETCHERS = {
    "greenhouse": fetch_greenhouse,
    "lever": fetch_lever,
    "ashby": fetch_ashby,
    "workable": fetch_workable,
    "bamboohr": fetch_bamboohr,
    "workday": fetch_workday,
    "recruitee": fetch_recruitee,
    "smartrecruiters": fetch_smartrecruiters,
    "breezy": fetch_breezy,
    "teamtailor": fetch_teamtailor,
    "freshteam": fetch_freshteam,
    "kula": fetch_kula,
    "rippling": fetch_rippling,
    "icims": fetch_icims,
    "oracle": fetch_oracle,
    "successfactors": fetch_successfactors,
}



async def process_company(
    session: aiohttp.ClientSession, company: dict, db_conn: sqlite3.Connection
) -> int:
    """Fetch jobs for one company and upsert them. Returns count of jobs found."""
    cid = company["id"]
    token = company["token"]
    ats = company["ats_type"]

    fetcher = ATS_FETCHERS.get(ats)
    if not fetcher:
        return 0

    jobs = await fetcher(session, token)
    now = _utc_now()

    inserted = 0
    try:
        for j in jobs:
            if not j.get("url"):
                continue
            loc_val = j.get("location") or "Unknown"
            title_val = j.get("title") or "Unknown Title"
            db_conn.execute(
                """
                INSERT INTO ats_crawler_jobs (company_id, title, location, url, jd_text, source, last_seen)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(url) DO UPDATE SET
                    title=excluded.title,
                    location=excluded.location,
                    last_seen=excluded.last_seen
                """,
                (cid, title_val, loc_val, j["url"], j.get("jd_text", ""), j["source"], now),
            )
            inserted += 1

        db_conn.execute(
            "UPDATE ats_companies SET last_scraped = ? WHERE id = ?", (now, cid)
        )
        db_conn.commit()
    except sqlite3.Error as e:
        logger.error(f"DB Error for {ats}/{token}: {e}")

    return inserted


# ─── Chunk Crawler ────────────────────────────────────────────────────────────

async def crawl_chunk(chunk_size: int = CHUNK_SIZE) -> dict:
    """Crawl one chunk of companies. Returns stats dict."""
    logger.info("[ats_crawler] Starting chunk crawl...")

    with get_conn() as conn:
        companies = conn.execute(
            """
            SELECT id, token, ats_type
            FROM ats_companies
            WHERE (status IS NULL OR status != 'invalid')
              AND (last_scraped IS NULL OR last_scraped = '' OR julianday('now') - julianday(last_scraped) > 1)
            ORDER BY RANDOM()
            LIMIT ?
            """,
            (chunk_size,),
        ).fetchall()
        companies = [dict(c) for c in companies]

    if not companies:
        logger.info("[ats_crawler] All companies are up-to-date.")
        return {"companies_crawled": 0, "jobs_found": 0}

    # Log ATS type distribution for this chunk
    ats_counts = {}
    for c in companies:
        ats_counts[c["ats_type"]] = ats_counts.get(c["ats_type"], 0) + 1
    logger.info(f"[ats_crawler] Crawling {len(companies)} companies: {ats_counts}")

    total_jobs = 0
    connector = aiohttp.TCPConnector(limit=CONCURRENCY)
    async with aiohttp.ClientSession(
        connector=connector, timeout=REQUEST_TIMEOUT
    ) as session:
        with get_conn() as db_conn:
            tasks = [process_company(session, c, db_conn) for c in companies]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for r in results:
                if isinstance(r, int):
                    total_jobs += r

    # Cleanup stale jobs (not seen in 7 days)
    with get_conn() as conn:
        deleted = conn.execute(
            "DELETE FROM ats_crawler_jobs WHERE julianday('now') - julianday(last_seen) > 7"
        ).rowcount
        if deleted:
            logger.info(f"[ats_crawler] Cleaned up {deleted} stale jobs")

    logger.info(f"[ats_crawler] Chunk complete: {len(companies)} companies → {total_jobs} jobs")
    return {"companies_crawled": len(companies), "jobs_found": total_jobs, "by_ats": ats_counts}


async def crawl_all(max_chunks: int = 30):
    """Run multiple chunks until all companies are crawled or max_chunks reached."""
    total_companies = 0
    total_jobs = 0

    for i in range(max_chunks):
        stats = await crawl_chunk()
        total_companies += stats["companies_crawled"]
        total_jobs += stats["jobs_found"]

        if stats["companies_crawled"] == 0:
            break

        logger.info(
            f"[ats_crawler] Progress: {total_companies} companies, {total_jobs} jobs after chunk {i+1}"
        )

    logger.info(
        f"[ats_crawler] DONE: Crawled {total_companies} companies, found {total_jobs} jobs total"
    )
    return {"total_companies": total_companies, "total_jobs": total_jobs}


def run_crawler():
    """Single chunk crawl (for cron/scheduler)."""
    asyncio.run(crawl_chunk())


def run_full_crawl():
    """Full crawl of all companies (for initial population)."""
    asyncio.run(crawl_all())


if __name__ == "__main__":
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    parser = argparse.ArgumentParser()
    parser.add_argument("--full", action="store_true", help="Run full crawl (all companies)")
    parser.add_argument("--chunks", type=int, default=30, help="Max chunks for full crawl")
    args = parser.parse_args()

    if args.full:
        asyncio.run(crawl_all(max_chunks=args.chunks))
    else:
        run_crawler()
