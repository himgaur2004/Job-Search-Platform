"""
ats_aggregator.py — Robust live ATS API fetcher for 7,500+ active verified company portals.

Supported ATS platforms:
  - Greenhouse (boards-api.greenhouse.io)
  - Lever (api.lever.co)
  - Ashby HQ (api.ashbyhq.com)
  - Workday (dynamicmyworkdayjobs.com endpoints)
  - Workable (apply.workable.com API)
  - BambooHR (subdomain.bamboohr.com/careers/list)
  - Oracle HCM (hcmRestApi)
  - iCIMS (api.icims.com)
"""
from __future__ import annotations

import html
import json
import logging
import random
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List
import requests

try:
    from agents.state import JobLead
except ImportError:
    JobLead = Dict[str, Any]

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
}

IND_CITIES = [
    "bengaluru", "bangalore", "mumbai", "delhi", "noida",
    "gurugram", "gurgaon", "hyderabad", "chennai", "pune", "india",
    "kolkata", "ahmedabad", "jaipur", "kochi", "indore", "chandigarh",
]

SYNONYMS = {
    "software developer": ["software engineer", "software developer", "sde", "software dev", "developer", "software development"],
    "software engineer": ["software engineer", "software developer", "sde", "software dev", "developer", "software development"],
    "sde": ["sde", "software engineer", "software developer", "software dev"],
    "frontend": ["frontend", "front-end", "front end", "react", "vue", "angular", "ui developer"],
    "frontend developer": ["frontend", "front-end", "front end", "react", "vue", "angular", "ui developer"],
    "frontend engineer": ["frontend", "front-end", "front end", "react", "vue", "angular", "ui engineer"],
    "backend": ["backend", "back-end", "back end", "node", "python", "java", "golang", "django"],
    "backend developer": ["backend", "back-end", "back end", "node", "python", "java", "golang", "django"],
    "backend engineer": ["backend", "back-end", "back end", "node", "python", "java", "golang", "django"],
    "fullstack": ["fullstack", "full-stack", "full stack", "fullstack engineer", "fullstack developer"],
    "fullstack developer": ["fullstack", "full-stack", "full stack", "fullstack engineer"],
    "data engineer": ["data engineer", "data engineering", "etl", "data analytics"],
    "qa engineer": ["qa", "quality assurance", "sdett", "sdet", "testing engineer", "test engineer"],
    "sdet": ["sdet", "sdett", "software developer in test", "qa engineer", "testing engineer"],
}


def _loc_match(job_loc: str, search_loc: str) -> bool:
    """Check if job location matches the target location. Accepts empty/unspecified locations as flexible."""
    if not search_loc or search_loc.lower() in ("any", "worldwide", ""):
        return True

    sl_list = [s.strip().lower() for s in search_loc.split(",") if s.strip()]

    # If job location is unspecified/empty, keep it (do not drop valid jobs!)
    if not job_loc or job_loc.strip() == "":
        return True

    jl = job_loc.lower()

    for sl in sl_list:
        if sl == "india" and ("india" in jl or any(c in jl for c in IND_CITIES)):
            return True
        if sl in jl:
            return True
        if "remote" in sl and ("remote" in jl or "anywhere" in jl or "worldwide" in jl or "work from home" in jl):
            return True

    return False


def _kw_match(title: str, keyword: str) -> bool:
    """Check if job title matches keyword using synonym expansion."""
    if not title:
        return False
    if not keyword or keyword.lower() == "any":
        return True

    t = title.lower()
    raw_kws = [k.strip().lower() for k in keyword.split(",") if k.strip()]

    for kw in raw_kws:
        if kw in SYNONYMS:
            if any(syn in t for syn in SYNONYMS[kw]):
                return True
        else:
            if kw in t:
                return True
            words = [w for w in kw.split() if len(w) > 2 and w not in ("software", "engineer", "developer", "and", "for")]
            if words and any(w in t for w in words):
                return True

    return False


def _normalize(company: str, title: str, loc: str, url: str, jd: str, source: str) -> JobLead | None:
    from services.job_sources import _normalize_job
    return _normalize_job(company=company, title=title, location=loc or "India / Remote", url=url, jd_text=jd, source=source)


# ─── Greenhouse ───────────────────────────────────────────────────────────────

def _clean_html(raw: str) -> str:
    """Strip HTML tags and decode entities to plain text."""
    if not raw:
        return ""
    try:
        from bs4 import BeautifulSoup
        return BeautifulSoup(raw, "lxml").get_text(separator=" ", strip=True)
    except Exception:
        return re.sub(r"<[^>]+>", " ", html.unescape(raw))


def _gh_fetch_detail_jd(token: str, job_id: int) -> str:
    """Fetch full JD from Greenhouse detail API."""
    try:
        resp = requests.get(
            f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs/{job_id}",
            timeout=4, headers=_HEADERS
        )
        if resp.ok:
            return _clean_html(resp.json().get("content", ""))
    except Exception:
        pass
    return ""


def fetch_greenhouse(company: dict, keyword: str, location: str) -> list[JobLead]:
    token = company["token"]
    name = company["name"]
    url = f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs"
    jobs = []
    try:
        resp = requests.get(url, timeout=5, headers=_HEADERS)
        if not resp.ok:
            return jobs
        data = resp.json()
        for j in data.get("jobs", []):
            title = j.get("title", "")
            loc = j.get("location", {}).get("name", "")
            link = j.get("absolute_url", "")
            job_id = j.get("id")
            if _loc_match(loc, location) and _kw_match(title, keyword):
                # Fetch full JD from detail API
                jd = _gh_fetch_detail_jd(token, job_id) if job_id else ""
                n = _normalize(name, title, loc, link, jd, "ats_greenhouse")
                if n:
                    jobs.append(n)
    except Exception as e:
        logger.debug(f"Greenhouse fetch failed for {name}: {e}")
    return jobs


# ─── Lever ───────────────────────────────────────────────────────────────────

def _lever_full_jd(j: dict) -> str:
    """Extract full JD text from a Lever posting JSON object."""
    desc = (j.get("descriptionPlain", "") or "") + " " + (j.get("descriptionBodyPlain", "") or "")
    lists = j.get("lists", [])
    if isinstance(lists, list):
        for l in lists:
            if isinstance(l, dict):
                desc += " " + (l.get("text", "") or "") + " " + _clean_html(l.get("content", "") or "")
    return desc.strip()


def fetch_lever(company: dict, keyword: str, location: str) -> list[JobLead]:
    token = company["token"]
    name = company["name"]
    url = f"https://api.lever.co/v0/postings/{token}"
    jobs = []
    try:
        resp = requests.get(url, timeout=5, headers=_HEADERS)
        if not resp.ok:
            return jobs
        data = resp.json()
        if not isinstance(data, list):
            return jobs
        for j in data:
            title = j.get("text", "")
            loc = j.get("categories", {}).get("location", "")
            link = j.get("hostedUrl", "")
            if _loc_match(loc, location) and _kw_match(title, keyword):
                jd = _lever_full_jd(j)
                n = _normalize(name, title, loc, link, jd, "ats_lever")
                if n:
                    jobs.append(n)
    except Exception as e:
        logger.debug(f"Lever fetch failed for {name}: {e}")
    return jobs


# ─── Ashby HQ ────────────────────────────────────────────────────────────────

def fetch_ashbyhq(company: dict, keyword: str, location: str) -> list[JobLead]:
    token = company["token"]
    name = company["name"]
    url = f"https://api.ashbyhq.com/posting-api/job-board/{token}"
    jobs = []
    try:
        resp = requests.get(url, timeout=5, headers=_HEADERS)
        if not resp.ok:
            return jobs
        data = resp.json()
        for j in data.get("jobs", []):
            title = j.get("title", "")
            loc = j.get("locationName") or j.get("location", "")
            link = j.get("jobUrl", "")
            if _loc_match(loc, location) and _kw_match(title, keyword):
                # Extract full JD from already-fetched board response
                jd = _clean_html(j.get("descriptionHtml", "") or j.get("descriptionPlain", "") or "")
                n = _normalize(name, title, loc, link, jd, "ats_ashby")
                if n:
                    jobs.append(n)
    except Exception as e:
        logger.debug(f"Ashby fetch failed for {name}: {e}")
    return jobs


# ─── Workable ────────────────────────────────────────────────────────────────

def fetch_workable(company: dict, keyword: str, location: str) -> list[JobLead]:
    token = company.get("token", "")
    name = company["name"]
    url = f"https://apply.workable.com/api/v3/accounts/{token}/jobs"
    jobs = []
    first_kw = keyword.split(",")[0].strip() if keyword else ""
    try:
        resp = requests.post(
            url,
            json={"query": first_kw, "location": []},
            timeout=5,
            headers=_HEADERS,
        )
        if not resp.ok:
            return jobs
        data = resp.json()
        for j in data.get("results", []):
            title = j.get("title", "")
            loc_info = j.get("location", {})
            loc = loc_info.get("location_str", "") if isinstance(loc_info, dict) else str(loc_info)
            shortcode = j.get("shortcode", "")
            link = f"https://apply.workable.com/{token}/j/{shortcode}/" if shortcode else ""
            if not link:
                continue
            if _loc_match(loc, location) and _kw_match(title, keyword):
                n = _normalize(name, title, loc, link, "", "ats_workable")
                if n:
                    jobs.append(n)
    except Exception as e:
        logger.debug(f"Workable fetch failed for {name}: {e}")
    return jobs


# ─── BambooHR ────────────────────────────────────────────────────────────────

def fetch_bamboohr(company: dict, keyword: str, location: str) -> list[JobLead]:
    token = company.get("token", "")
    name = company["name"]
    url = f"https://{token}.bamboohr.com/careers/list"
    jobs = []
    try:
        resp = requests.get(url, timeout=5, headers={**_HEADERS, "Accept": "application/json"})
        if not resp.ok:
            return jobs
        data = resp.json()
        for j in data.get("result", []):
            title = j.get("jobOpeningName", "")
            dept_id = j.get("id", "")
            loc_info = j.get("location", {})
            city = loc_info.get("city", "") if isinstance(loc_info, dict) else ""
            link = f"https://{token}.bamboohr.com/careers/{dept_id}" if dept_id else ""
            if not link:
                continue
            if _loc_match(city, location) and _kw_match(title, keyword):
                n = _normalize(name, title, city, link, "", "ats_bamboohr")
                if n:
                    jobs.append(n)
    except Exception as e:
        logger.debug(f"BambooHR fetch failed for {name}: {e}")
    return jobs


# ─── Workday ──────────────────────────────────────────────────────────────────

def fetch_workday(company: dict, keyword: str, location: str) -> list[JobLead]:
    tenant = company.get("token", "")
    name = company["name"]
    if not tenant:
        return []

    clusters = ["wd1", "wd3", "wd5", "wd12"]
    sites = ["External", "Careers", "CX_1", "CX_2", "CorporateCareers", tenant]
    first_kw = keyword.split(",")[0].strip() if keyword else ""

    payload = {
        "appliedFacets": {},
        "limit": 20,
        "offset": 0,
        "searchText": first_kw,
    }

    jobs = []
    headers = {**_HEADERS, "Content-Type": "application/json"}

    for cluster in clusters:
        domain = f"{tenant}.{cluster}.myworkdayjobs.com"
        for site in sites:
            url = f"https://{domain}/wday/cxs/{tenant}/{site}/jobs"
            try:
                resp = requests.post(url, json=payload, headers=headers, timeout=3)
                if resp.status_code == 200:
                    data = resp.json()
                    postings = data.get("jobPostings", [])
                    if postings:
                        for j in postings:
                            title = j.get("title", "")
                            loc = j.get("locationsText", "")
                            path = j.get("externalPath", "")
                            link = f"https://{domain}{path}" if path else ""
                            if link and _loc_match(loc, location) and _kw_match(title, keyword):
                                n = _normalize(name, title, loc, link, "", "ats_workday")
                                if n:
                                    jobs.append(n)
                        if jobs:
                            return jobs
            except Exception:
                continue
    return jobs


# ─── Oracle HCM ──────────────────────────────────────────────────────────────

def fetch_oracle(company: dict, keyword: str, location: str) -> list[JobLead]:
    domain = company.get("domain") or f"{company['token']}.oraclecloud.com"
    site = company.get("site", "CX_1")
    name = company["name"]
    url = (
        f"https://{domain}/hcmRestApi/resources/latest/recruitingCEJobRequisitions"
        f"?onlyData=true&expand=requisitionList&finder=findReqs;siteNumber={site},limit=200"
    )
    jobs = []
    try:
        resp = requests.get(url, timeout=5, headers=_HEADERS)
        if not resp.ok:
            return jobs
        data = resp.json()
        items = data.get("items", [])
        if not items or "requisitionList" not in items[0]:
            return jobs
        for j in items[0]["requisitionList"]:
            title = j.get("Title", "")
            loc = j.get("PrimaryLocation", "")
            link = f"https://{domain}/hcmUI/CandidateExperience/en/sites/{site}/job/{j.get('Id')}"
            if _loc_match(loc, location) and _kw_match(title, keyword):
                n = _normalize(name, title, loc, link, "", "ats_oracle")
                if n:
                    jobs.append(n)
    except Exception as e:
        logger.debug(f"Oracle fetch failed for {name}: {e}")
    return jobs


# ─── iCIMS ───────────────────────────────────────────────────────────────────

def fetch_icims(company: dict, keyword: str, location: str) -> list[JobLead]:
    token = company.get("token", "")
    name = company["name"]
    first_kw = keyword.split(",")[0].strip() if keyword else ""
    url = f"https://api.icims.com/customers/{token}/jobs?icsearchfield=jobtitle&icsearchvalue={first_kw}"
    jobs = []
    try:
        resp = requests.get(url, timeout=5, headers=_HEADERS)
        if not resp.ok:
            return jobs
        data = resp.json()
        for j in data.get("searchResults", []):
            title = j.get("jobtitle", "")
            loc_info = j.get("joblocation", {})
            loc = loc_info.get("value", "") if isinstance(loc_info, dict) else str(loc_info)
            job_id = j.get("id", "")
            link = f"https://careers.icims.com/jobs/{token}/{job_id}/job" if job_id else ""
            if not link:
                continue
            if _loc_match(loc, location) and _kw_match(title, keyword):
                n = _normalize(name, title, loc, link, "", "ats_icims")
                if n:
                    jobs.append(n)
    except Exception as e:
        logger.debug(f"iCIMS fetch failed for {name}: {e}")
    return jobs


# ─── Recruitee ───────────────────────────────────────────────────────────────

def fetch_recruitee(company: dict, keyword: str, location: str) -> list[JobLead]:
    token = company.get("token", "")
    name = company["name"]
    url = f"https://api.recruitee.com/c/{token}/careers/offers"
    jobs = []
    try:
        resp = requests.get(url, timeout=5, headers=_HEADERS)
        if not resp.ok:
            return jobs
        data = resp.json()
        for j in data.get("offers", []):
            title = j.get("title", "")
            loc = j.get("location", "") or j.get("city", "")
            link = j.get("careers_url", "")
            if link and _loc_match(str(loc), location) and _kw_match(title, keyword):
                n = _normalize(name, title, str(loc), link, j.get("description", "")[:300], "ats_recruitee")
                if n:
                    jobs.append(n)
    except Exception as e:
        logger.debug(f"Recruitee fetch failed for {name}: {e}")
    return jobs


# ─── SmartRecruiters ─────────────────────────────────────────────────────────

def fetch_smartrecruiters(company: dict, keyword: str, location: str) -> list[JobLead]:
    token = company.get("token", "")
    name = company["name"]
    url = f"https://api.smartrecruiters.com/v1/companies/{token}/postings"
    jobs = []
    try:
        resp = requests.get(url, timeout=5, headers=_HEADERS)
        if not resp.ok:
            return jobs
        data = resp.json()
        for j in data.get("content", []):
            title = j.get("name", "")
            loc_info = j.get("location", {})
            city = loc_info.get("city", "") if isinstance(loc_info, dict) else ""
            country = loc_info.get("country", "") if isinstance(loc_info, dict) else ""
            loc = f"{city}, {country}".strip(", ")
            job_id = j.get("id", "")
            link = f"https://jobs.smartrecruiters.com/{token}/{job_id}" if job_id else ""
            if link and _loc_match(loc, location) and _kw_match(title, keyword):
                n = _normalize(name, title, loc, link, "", "ats_smartrecruiters")
                if n:
                    jobs.append(n)
    except Exception as e:
        logger.debug(f"SmartRecruiters fetch failed for {name}: {e}")
    return jobs


# ─── Breezy HR ───────────────────────────────────────────────────────────────

def fetch_breezy(company: dict, keyword: str, location: str) -> list[JobLead]:
    token = company.get("token", "")
    name = company["name"]
    url = f"https://{token}.breezy.hr/api/positions"
    jobs = []
    try:
        resp = requests.get(url, timeout=5, headers=_HEADERS)
        if not resp.ok:
            return jobs
        data = resp.json()
        if isinstance(data, list):
            for j in data:
                title = j.get("name", "")
                loc_info = j.get("location", {})
                name_loc = loc_info.get("name", "") if isinstance(loc_info, dict) else ""
                friendly_id = j.get("friendly_id", "")
                link = f"https://{token}.breezy.hr/p/{friendly_id}" if friendly_id else ""
                if link and _loc_match(name_loc, location) and _kw_match(title, keyword):
                    n = _normalize(name, title, name_loc, link, "", "ats_breezy")
                    if n:
                        jobs.append(n)
    except Exception as e:
        logger.debug(f"Breezy fetch failed for {name}: {e}")
    return jobs


# ─── Teamtailor ──────────────────────────────────────────────────────────────

def fetch_teamtailor(company: dict, keyword: str, location: str) -> list[JobLead]:
    token = company.get("token", "")
    name = company["name"]
    url = f"https://{token}.teamtailor.com/jobs.json"
    jobs = []
    try:
        resp = requests.get(url, timeout=5, headers=_HEADERS)
        if not resp.ok:
            return jobs
        data = resp.json()
        for j in data.get("data", []):
            attrs = j.get("attributes", {})
            title = attrs.get("title", "")
            loc = attrs.get("location-name", "")
            link = attrs.get("careersite-job-url", "")
            if link and _loc_match(loc, location) and _kw_match(title, keyword):
                n = _normalize(name, title, loc, link, "", "ats_teamtailor")
                if n:
                    jobs.append(n)
    except Exception as e:
        logger.debug(f"Teamtailor fetch failed for {name}: {e}")
    return jobs


# ─── Freshteam ───────────────────────────────────────────────────────────────

def fetch_freshteam(company: dict, keyword: str, location: str) -> list[JobLead]:
    token = company.get("token", "")
    name = company["name"]
    url = f"https://{token}.freshteam.com/jobs.json"
    jobs = []
    try:
        resp = requests.get(url, timeout=5, headers=_HEADERS)
        if not resp.ok:
            return jobs
        data = resp.json()
        if isinstance(data, list):
            for j in data:
                title = j.get("title", "")
                loc = j.get("location", "")
                job_id = j.get("id", "")
                link = f"https://{token}.freshteam.com/jobs/{job_id}" if job_id else ""
                if link and _loc_match(loc, location) and _kw_match(title, keyword):
                    n = _normalize(name, title, loc, link, "", "ats_freshteam")
                    if n:
                        jobs.append(n)
    except Exception as e:
        logger.debug(f"Freshteam fetch failed for {name}: {e}")
    return jobs


# ─── Kula ATS ────────────────────────────────────────────────────────────────

def fetch_kula(company: dict, keyword: str, location: str) -> list[JobLead]:
    token = company.get("token", "")
    name = company["name"]
    url = f"https://api.kula.ai/v1/job-board/{token}/jobs"
    jobs = []
    try:
        resp = requests.get(url, timeout=5, headers=_HEADERS)
        if not resp.ok:
            return jobs
        data = resp.json()
        for j in data.get("jobs", []):
            title = j.get("title", "")
            loc = j.get("location", "")
            link = j.get("applyUrl") or f"https://{token}.kula.ai/jobs/{j.get('id')}"
            if link and _loc_match(loc, location) and _kw_match(title, keyword):
                n = _normalize(name, title, loc, link, "", "ats_kula")
                if n:
                    jobs.append(n)
    except Exception as e:
        logger.debug(f"Kula fetch failed for {name}: {e}")
    return jobs


# ─── Rippling ATS ─────────────────────────────────────────────────────────────

def fetch_rippling(company: dict, keyword: str, location: str) -> list[JobLead]:
    token = company.get("token", "")
    name = company["name"]
    url = f"https://ats.rippling.com/api/v1/board/{token}/jobs"
    jobs = []
    try:
        resp = requests.get(url, timeout=5, headers=_HEADERS)
        if not resp.ok:
            return jobs
        data = resp.json()
        if isinstance(data, list):
            for j in data:
                title = j.get("name", "")
                loc_obj = j.get("workLocation", {})
                loc = loc_obj.get("label", "") if isinstance(loc_obj, dict) else str(loc_obj)
                link = j.get("url") or f"https://ats.rippling.com/{token}/jobs/{j.get('uuid')}"
                if link and _loc_match(loc, location) and _kw_match(title, keyword):
                    n = _normalize(name, title, loc, link, "", "ats_rippling")
                    if n:
                        jobs.append(n)
    except Exception as e:
        logger.debug(f"Rippling fetch failed for {name}: {e}")
    return jobs


# ─── Dispatcher ───────────────────────────────────────────────────────────────

ATS_DISPATCH = {
    "greenhouse": fetch_greenhouse,
    "lever": fetch_lever,
    "ashby": fetch_ashbyhq,
    "workable": fetch_workable,
    "bamboohr": fetch_bamboohr,
    "workday": fetch_workday,
    "oracle": fetch_oracle,
    "icims": fetch_icims,
    "recruitee": fetch_recruitee,
    "smartrecruiters": fetch_smartrecruiters,
    "breezy": fetch_breezy,
    "teamtailor": fetch_teamtailor,
    "freshteam": fetch_freshteam,
    "kula": fetch_kula,
    "rippling": fetch_rippling,
}


def fetch_all_ats(keyword: str, location: str, limit_companies: int = 1500) -> list[JobLead]:
    """
    Fetch live jobs directly from active ATS API endpoints in parallel.
    Queries up to limit_companies active companies concurrently.
    """
    from services.db import get_conn

    companies = []
    try:
        with get_conn() as conn:
            # 1. Always select ALL non-Greenhouse/Lever startup ATS companies first (Kula, Ashby, Workable, Breezy, Freshteam, Rippling, etc.)
            startup_rows = conn.execute(
                "SELECT name, ats_type as ats, token FROM ats_companies WHERE status = 'active' AND ats_type NOT IN ('greenhouse', 'lever') ORDER BY CASE WHEN last_scraped IS NULL THEN 0 ELSE 1 END, last_scraped ASC"
            ).fetchall()
            
            # 2. Select Greenhouse and Lever companies systematically by least recently scraped
            remaining_limit = max(500, limit_companies - len(startup_rows))
            gh_lever_rows = conn.execute(
                "SELECT name, ats_type as ats, token FROM ats_companies WHERE status = 'active' AND ats_type IN ('greenhouse', 'lever') ORDER BY CASE WHEN last_scraped IS NULL THEN 0 ELSE 1 END, last_scraped ASC LIMIT ?",
                (remaining_limit,)
            ).fetchall()

            companies = [dict(r) for r in (startup_rows + gh_lever_rows)]
    except Exception as e:
        logger.warning(f"DB load for ATS companies failed: {e}")

    if not companies:
        return []

    all_jobs: list[JobLead] = []
    random.shuffle(companies)

    executor = ThreadPoolExecutor(max_workers=200)
    futures = []
    for comp in companies:
        ats_type = comp.get("ats", "")
        fn = ATS_DISPATCH.get(ats_type)
        if fn:
            futures.append(executor.submit(fn, comp, keyword, location))

    try:
        for future in as_completed(futures, timeout=25):
            try:
                res = future.result()
                all_jobs.extend(res)
            except Exception:
                pass
    except TimeoutError:
        logger.info("[ats_aggregator] Live ATS fetch 25s limit reached. Returning results.")
    finally:
        executor.shutdown(wait=False, cancel_futures=True)

    logger.info(f"[ats_aggregator] Total live jobs fetched from {len(companies)} ATS APIs: {len(all_jobs)}")
    return all_jobs
