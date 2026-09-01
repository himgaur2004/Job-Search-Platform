from __future__ import annotations

import os
import re
import time
import random
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential

from agents.state import JobLead
from services.resilience import CircuitBreaker
from services.db import get_conn


@dataclass
class SourceResult:
    jobs: list[JobLead]
    errors: list[str]


_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

_remoteok_breaker = CircuitBreaker("remoteok")
_remotive_breaker = CircuitBreaker("remotive")
_indeed_breaker = CircuitBreaker("indeed")
_wellfound_breaker = CircuitBreaker("wellfound")
_glassdoor_breaker = CircuitBreaker("glassdoor")


@retry(wait=wait_exponential(min=2, max=15), stop=stop_after_attempt(3), reraise=True)
def _get_json(url: str) -> Any:
    response = requests.get(url, timeout=20, headers=_HEADERS)
    response.raise_for_status()
    return response.json()


def _get_html(url: str, timeout: int = 30000) -> BeautifulSoup:
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
        )
        ctx = browser.new_context(
            user_agent=_HEADERS["User-Agent"],
            viewport={"width": 1440, "height": 900},
        )
        page = ctx.new_page()
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=timeout)
            # Give it a second to run JS challenges
            page.wait_for_timeout(2000)
            content = page.content()
        finally:
            browser.close()
    return BeautifulSoup(content, "lxml")


def _normalize_job(
    *,
    company: str,
    title: str,
    location: str,
    url: str,
    jd_text: str,
    source: str,
) -> JobLead | None:
    if not company or not title or not url:
        return None
    return {
        "company": company.strip(),
        "title": title.strip(),
        "location": location.strip(),
        "url": url.strip(),
        "jd_text": jd_text.strip(),
        "source": source,
    }


# ─── RemoteOK ────────────────────────────────────────────────────────────────

def _fetch_remoteok(limit: int) -> SourceResult:
    if not _remoteok_breaker.allow():
        return SourceResult(jobs=[], errors=["remoteok circuit open; skipping."])
    try:
        payload = _get_json("https://remoteok.com/api")
    except requests.RequestException as exc:
        _remoteok_breaker.record_failure()
        return SourceResult(jobs=[], errors=[f"remoteok failed: {exc}"])

    if not isinstance(payload, list):
        _remoteok_breaker.record_failure()
        return SourceResult(jobs=[], errors=["remoteok payload invalid."])

    jobs: list[JobLead] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        normalized = _normalize_job(
            company=str(item.get("company", "")),
            title=str(item.get("position", "")),
            location=str(item.get("location", "Remote")),
            url=str(item.get("url", "")),
            jd_text=str(item.get("description", "")),
            source="remoteok",
        )
        if normalized:
            jobs.append(normalized)
        if len(jobs) >= limit:
            break
    _remoteok_breaker.record_success()
    return SourceResult(jobs=jobs, errors=[])


# ─── Remotive ────────────────────────────────────────────────────────────────

def _fetch_remotive(limit: int) -> SourceResult:
    if not _remotive_breaker.allow():
        return SourceResult(jobs=[], errors=["remotive circuit open; skipping."])
    try:
        payload = _get_json("https://remotive.com/api/remote-jobs")
    except requests.RequestException as exc:
        _remotive_breaker.record_failure()
        return SourceResult(jobs=[], errors=[f"remotive failed: {exc}"])

    if not isinstance(payload, dict) or not isinstance(payload.get("jobs"), list):
        _remotive_breaker.record_failure()
        return SourceResult(jobs=[], errors=["remotive payload invalid."])

    jobs: list[JobLead] = []
    for item in payload["jobs"]:
        if not isinstance(item, dict):
            continue
        normalized = _normalize_job(
            company=str(item.get("company_name", "")),
            title=str(item.get("title", "")),
            location=str(item.get("candidate_required_location", "Remote")),
            url=str(item.get("url", "")),
            jd_text=str(item.get("description", "")),
            source="remotive",
        )
        if normalized:
            jobs.append(normalized)
        if len(jobs) >= limit:
            break
    _remotive_breaker.record_success()
    return SourceResult(jobs=jobs, errors=[])


# ─── Indeed ──────────────────────────────────────────────────────────────────

def _fetch_indeed(keyword: str, location: str, limit: int) -> SourceResult:
    if not _indeed_breaker.allow():
        return SourceResult(jobs=[], errors=["indeed circuit open; skipping."])
    try:
        domain = "www.indeed.com"
        loc_lower = location.lower()
        if "india" in loc_lower or any(c in loc_lower for c in ["bengaluru", "bangalore", "mumbai", "delhi", "noida", "gurugram", "hyderabad", "chennai", "pune"]):
            domain = "in.indeed.com"

        url = (
            f"https://{domain}/jobs"
            f"?q={quote_plus(keyword)}&l={quote_plus(location)}&sort=date"
        )
        soup = _get_html(url)
        jobs: list[JobLead] = []

        cards = soup.select(".resultContent")
        for card in cards[:limit]:
            title_tag = card.select_one("[id^='jobTitle'], .jobTitle")
            company_tag = card.select_one("[data-testid='company-name']")
            location_tag = card.select_one("[data-testid='text-location']")
            jk_node = card.select_one("[data-jk]")
            job_key = jk_node.get("data-jk", "") if jk_node else ""

            title = title_tag.get_text(strip=True) if title_tag else ""
            company = company_tag.get_text(strip=True) if company_tag else ""
            loc = location_tag.get_text(strip=True) if location_tag else location
            job_url = f"https://www.indeed.com/viewjob?jk={job_key}" if job_key else ""

            normalized = _normalize_job(
                company=company, title=title, location=loc,
                url=job_url, jd_text="", source="indeed"
            )
            if normalized:
                jobs.append(normalized)

        _indeed_breaker.record_success()
        return SourceResult(jobs=jobs, errors=[])
    except Exception as exc:
        _indeed_breaker.record_failure()
        return SourceResult(jobs=[], errors=[f"indeed failed: {exc}"])


# ─── Wellfound (AngelList) ────────────────────────────────────────────────────

def _fetch_wellfound(keyword: str, limit: int) -> SourceResult:
    if not _wellfound_breaker.allow():
        return SourceResult(jobs=[], errors=["wellfound circuit open; skipping."])
    try:
        # Wellfound has a public job listing page
        url = f"https://wellfound.com/jobs?q={quote_plus(keyword)}"
        soup = _get_html(url, timeout=60000)
        jobs: list[JobLead] = []

        # Wellfound renders via JS, but basic cards are in the initial HTML
        cards = soup.select("div[class*='styles_jobCard']") or soup.select("[data-test='JobListing']")
        if not cards:
            # Fallback: use their public talent API
            api_url = f"https://wellfound.com/company_filters/search_startup_talent?q={quote_plus(keyword)}&page=1"
            resp = requests.get(api_url, headers=_HEADERS, timeout=20)
            if resp.ok:
                data = resp.json()
                for item in data.get("startup_roles", [])[:limit]:
                    normalized = _normalize_job(
                        company=item.get("startup", {}).get("name", ""),
                        title=item.get("title", ""),
                        location=item.get("location", "Remote"),
                        url=f"https://wellfound.com/jobs/{item.get('id', '')}",
                        jd_text=item.get("description", ""),
                        source="wellfound",
                    )
                    if normalized:
                        jobs.append(normalized)
        else:
            for card in cards[:limit]:
                title_tag = card.select_one("h2, [class*='title']")
                company_tag = card.select_one("[class*='company'], [class*='startup']")
                loc_tag = card.select_one("[class*='location']")
                link_tag = card.select_one("a[href*='/jobs/']")

                title = title_tag.get_text(strip=True) if title_tag else ""
                company = company_tag.get_text(strip=True) if company_tag else ""
                loc = loc_tag.get_text(strip=True) if loc_tag else "Remote"
                href = link_tag.get("href", "") if link_tag else ""
                job_url = f"https://wellfound.com{href}" if href.startswith("/") else href

                normalized = _normalize_job(
                    company=company, title=title, location=loc,
                    url=job_url, jd_text="", source="wellfound"
                )
                if normalized:
                    jobs.append(normalized)

        _wellfound_breaker.record_success()
        return SourceResult(jobs=jobs, errors=[])
    except Exception as exc:
        _wellfound_breaker.record_failure()
        return SourceResult(jobs=[], errors=[f"wellfound failed: {exc}"])


# ─── Glassdoor ───────────────────────────────────────────────────────────────

def _fetch_glassdoor(keyword: str, location: str, limit: int) -> SourceResult:
    if not _glassdoor_breaker.allow():
        return SourceResult(jobs=[], errors=["glassdoor circuit open; skipping."])
    try:
        url = (
            f"https://www.glassdoor.com/Job/jobs.htm"
            f"?sc.keyword={quote_plus(keyword)}&locT=N&locId=0&jobType=all"
        )
        soup = _get_html(url, timeout=60000)
        jobs: list[JobLead] = []

        cards = soup.select("li[data-test='jobListing']") or soup.select("[id^='job-listing']")
        for card in cards[:limit]:
            title_tag = card.select_one("[data-test='job-title'], a.jobLink")
            company_tag = card.select_one("[data-test='employer-name']")
            loc_tag = card.select_one("[data-test='emp-location']")
            link_tag = card.select_one("a[href*='/job-listing/']") or card.select_one("a.jobLink")

            title = title_tag.get_text(strip=True) if title_tag else ""
            company = company_tag.get_text(strip=True) if company_tag else ""
            loc = loc_tag.get_text(strip=True) if loc_tag else location
            href = link_tag.get("href", "") if link_tag else ""
            job_url = f"https://www.glassdoor.com{href}" if href.startswith("/") else href

            normalized = _normalize_job(
                company=company, title=title, location=loc,
                url=job_url, jd_text="", source="glassdoor"
            )
            if normalized:
                jobs.append(normalized)

        _glassdoor_breaker.record_success()
        return SourceResult(jobs=jobs, errors=[])
    except Exception as exc:
        _glassdoor_breaker.record_failure()
        return SourceResult(jobs=[], errors=[f"glassdoor failed: {exc}"])


# ─── LinkedIn (via guest API) ─────────────────────────────────────────────────

def _fetch_linkedin(keyword: str, location: str, limit: int) -> SourceResult:
    try:
        from services.linkedin import search_jobs
        raw = search_jobs(keyword, location, limit=limit)
        jobs = [
            _normalize_job(
                company=r["company"], title=r["title"],
                location=r.get("location", location),
                url=r["url"], jd_text="", source="linkedin"
            )
            for r in raw
        ]
        return SourceResult(jobs=[j for j in jobs if j], errors=[])
    except Exception as exc:
        return SourceResult(jobs=[], errors=[f"linkedin failed: {exc}"])


# ─── Experience Parser Helper ──────────────────────────────────────────────────

def _parse_max_years(raw: str) -> int | None:
    if not raw:
        return None
    r = raw.lower().strip()
    if r in ("any", "any experience", ""):
        return None
    match = re.search(r"(\d+)", r)
    if match:
        upper_match = re.search(r"\d+\s*-\s*(\d+)", r)
        if upper_match:
            return int(upper_match.group(1))
        return int(match.group(1))
    if any(x in r for x in ("fresher", "entry", "junior", "trainee", "intern", "new grad")):
        return 2
    if "mid" in r:
        return 5
    return None


# ─── Unified fetch ────────────────────────────────────────────────────────────

def _fetch_ats_db(keyword: str, location: str, limit: int = 1000, experience: str = "0") -> SourceResult:
    """Queries the local background-crawled SQLite database for direct ATS links.
    
    Uses smart keyword synonym expansion (e.g. 'Software Developer' matches 'Software Engineer', 'SDE', 'Developer', etc.)
    Handles India-specific location matching (Bengaluru, Pune, Hyderabad, etc.)
    """
    jobs: list[JobLead] = []
    
    raw_kw = keyword.strip()
    loc_lower = location.lower().replace("remote", "").strip()
    max_years = _parse_max_years(experience)
    
    # Industry synonym mappings
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
        "full stack developer": ["fullstack", "full-stack", "full stack", "fullstack engineer"],
        "data engineer": ["data engineer", "data engineering", "etl", "data analytics"],
        "qa engineer": ["qa", "quality assurance", "sdett", "sdet", "testing engineer", "test engineer"],
        "sdet": ["sdet", "sdett", "software developer in test", "qa engineer", "testing engineer"],
    }
    
    # India city mapping for smart location matching
    INDIA_CITIES = [
        "india", "bengaluru", "bangalore", "pune", "hyderabad",
        "chennai", "mumbai", "ncr", "delhi", "noida",
        "gurugram", "gurgaon", "kolkata", "ahmedabad", "kochi",
        "thiruvananthapuram", "jaipur", "chandigarh", "indore",
        "coimbatore", "nagpur", "lucknow", "bhubaneswar",
    ]
    
    with get_conn() as conn:
        query = """
            SELECT COALESCE(c.name, cc.name, replace(replace(j.source, 'ats_', ''), 'custom_', '')) as company_name,
                   j.title, j.location, j.url, j.jd_text, j.source
            FROM ats_crawler_jobs j
            LEFT JOIN ats_companies c ON j.company_id = c.id
            LEFT JOIN companies_custom cc ON (j.company_id IS NULL AND (j.url LIKE '%' || cc.domain || '%' OR lower(j.jd_text) LIKE '%' || lower(cc.name) || '%'))
            WHERE 1=1
        """
        params = []
        
        # Experience level exclusions at SQL query level
        if max_years is not None and max_years <= 2:
            query += """ AND (
                lower(j.title) NOT LIKE '%senior%' AND
                lower(j.title) NOT LIKE '%sr.%' AND
                lower(j.title) NOT LIKE '%staff%' AND
                lower(j.title) NOT LIKE '%lead%' AND
                lower(j.title) NOT LIKE '%principal%' AND
                lower(j.title) NOT LIKE '%manager%' AND
                lower(j.title) NOT LIKE '%director%' AND
                lower(j.title) NOT LIKE '%head%' AND
                lower(j.title) NOT LIKE '%architect%' AND
                lower(j.title) NOT LIKE '% ii%' AND
                lower(j.title) NOT LIKE '% iii%' AND
                lower(j.title) NOT LIKE '% iv%' AND
                lower(j.title) NOT LIKE '% 2%' AND
                lower(j.title) NOT LIKE '% 3%'
            )"""

        # Build Keyword Filter
        phrases = [p.strip().lower() for p in raw_kw.split(",") if p.strip()]
        kw_clauses = []
        for phrase in phrases:
            phrase_clauses = []
            if phrase in SYNONYMS:
                for syn in SYNONYMS[phrase]:
                    phrase_clauses.append("lower(j.title) LIKE ?")
                    params.append(f"%{syn}%")
            else:
                phrase_clauses.append("lower(j.title) LIKE ?")
                params.append(f"%{phrase}%")

                # If multi-word phrase like 'react developer', also match individual tech tokens
                words = [w.strip() for w in phrase.split() if len(w.strip()) >= 2 and w.strip() not in ("developer", "engineer", "software", "developer", "dev", "sde", "role", "jobs", "job")]
                if words:
                    sub_clauses = []
                    for w in words:
                        sub_clauses.append("lower(j.title) LIKE ?")
                        params.append(f"%{w}%")
                    if sub_clauses:
                        phrase_clauses.append("(" + " AND ".join(sub_clauses) + ")")

            if phrase_clauses:
                kw_clauses.append("(" + " OR ".join(phrase_clauses) + ")")
        
        if kw_clauses:
            query += " AND (" + " OR ".join(kw_clauses) + ")"
        
        # Location filter
        if loc_lower and loc_lower not in ["any", "worldwide", ""]:
            if loc_lower == "india" or loc_lower in INDIA_CITIES:
                city_clauses = " OR ".join(
                    f"lower(j.location) LIKE '%{city}%'" for city in INDIA_CITIES
                )
                query += f" AND ({city_clauses})"
            elif "remote" in loc_lower:
                query += " AND lower(j.location) LIKE '%remote%'"
            else:
                query += " AND lower(j.location) LIKE ?"
                params.append(f"%{loc_lower}%")
        
        query += " ORDER BY j.last_seen DESC LIMIT ?"
        params.append(limit)
        
        rows = conn.execute(query, params).fetchall()
        
        for row in rows:
            comp = row["company_name"]
            if not comp or comp.strip() == "" or comp.lower() in ("custom_regex", "custom_llm", "ats_crawler"):
                # Derive company name from domain URL
                from urllib.parse import urlparse
                parsed = urlparse(row["url"])
                domain = parsed.netloc.replace("www.", "").split(".")[0].capitalize()
                comp = domain if domain else "Startup"

            norm = _normalize_job(
                company=comp,
                title=row["title"],
                location=row["location"],
                url=row["url"],
                jd_text=row["jd_text"],
                source=row["source"]
            )
            if norm:
                jobs.append(norm)
                
    return SourceResult(jobs=jobs, errors=[])

def fetch_jobs_from_all_sources(
    keyword: str = "Software Engineer",
    location: str = "Remote",
    experience: str = "Any",
    search_type: str = "all"
) -> SourceResult:
    """Fetch from all sources in parallel and merge, deduplicating by URL and filtering by experience."""
    import concurrent.futures

    if os.getenv("ENABLE_REMOTE_FETCH", "true").lower() != "true":
        return SourceResult(jobs=[], errors=[])

    per_source = int(os.getenv("MAX_JOBS_PER_SOURCE", "25"))

    tasks = {}
    if search_type in ("all", "job_boards", "linkedin", "wellfound"):
        from services.linkedin_hr_scout import fetch_linkedin_hr_posts
        from services.wellfound_scout import fetch_wellfound_jobs
        tasks.update({
            "linkedin": lambda: _fetch_linkedin(keyword, location, per_source),
            "linkedin_hr_scout": lambda: SourceResult(jobs=fetch_linkedin_hr_posts(keyword, location, per_source), errors=[]),
            "wellfound": lambda: SourceResult(jobs=fetch_wellfound_jobs(keyword, location, per_source), errors=[]),
            "remoteok":  lambda: _fetch_remoteok(per_source),
            "remotive":  lambda: _fetch_remotive(per_source),
            "indeed":    lambda: _fetch_indeed(keyword, location, per_source),
        })
    if search_type in ("all", "ats"):
        from services.ats_aggregator import fetch_all_ats
        tasks["ats_db"] = lambda: _fetch_ats_db(keyword, location, 1000, experience=experience)
        tasks["ats_live"] = lambda: SourceResult(jobs=fetch_all_ats(keyword, location, limit_companies=400), errors=[])

    results: dict[str, SourceResult] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(tasks) or 1) as ex:
        futures = {ex.submit(fn): name for name, fn in tasks.items()}
        for future in concurrent.futures.as_completed(futures, timeout=120):
            name = futures[future]
            try:
                results[name] = future.result()
            except Exception as exc:
                results[name] = SourceResult(jobs=[], errors=[f"{name} thread error: {exc}"])

    all_jobs: list[JobLead] = []
    all_errors: list[str] = []
    seen_urls: set[str] = set()

    for name, result in results.items():
        all_errors.extend(result.errors)
        for job in result.jobs:
            url = job.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                all_jobs.append(job)

    # ── Fetch missing JDs before experience filtering ────────────────────────
    # This is the critical step: without full JDs, the experience regex sees
    # empty text and lets everything through (including 5+ year roles).
    try:
        import asyncio
        from services.jd_fetcher import batch_fetch_missing_jds
        all_jobs = asyncio.run(batch_fetch_missing_jds(all_jobs))
    except Exception as e:
        all_errors.append(f"jd_fetcher failed: {e}")

    # ── Experience filter ────────────────────────────────────────────────────
    def _parse_max_years(raw: str) -> int | None:
        r = raw.lower().strip()
        if r in ("any", "any experience", ""):
            return None
        # Extract explicit digit if provided (e.g. "0", "0 years", "1", "2", "3", "0-2 yrs")
        match = re.search(r"(\d+)", r)
        if match:
            # If string is "0-2 yrs", group 1 is 0. If "3-5 yrs", group 1 is 3, but let's check upper bound
            upper_match = re.search(r"\d+\s*-\s*(\d+)", r)
            if upper_match:
                return int(upper_match.group(1))
            return int(match.group(1))
        if any(x in r for x in ("fresher", "entry", "junior", "trainee", "intern", "new grad")):
            return 2
        if "mid" in r:
            return 5
        return None

    max_years = _parse_max_years(experience)

    # Non-engineering roles to strictly EXCLUDE
    NON_TECH_EXCLUSIONS = [
        "sales", "support", "customer", "tele-sales", "recruiter", "hr ", "designer",
        "product designer", "marketing", "accountant", "legal", "content", "writer",
        "agent", "representative", "operations", "business analyst", "fincrime", "sar analyst",
        "inside sales", "support agent", "kyc analyst", "product manager", "project manager",
        "talent", "people", "brand", "creative", "editorial", "video editor", "business intern",
        "biomedical", "firmware test", "learning & development", "learning and development",
        "consultant", "security consultant", "data curation", "ux design", "powerbi",
        "manual", "copywriter", "graphic", "social media", "product management",
        "internal audit", "internal communications", "growth management", "ta enabling",
        "employee engagement", "risk advisory", "category manager", "supply chain",
        "finance", "partnerships"
    ]

    SENIOR_EXCLUSIONS = [
        "senior", "sr.", "sr ", "staff", "lead", "principal", "principle", "manager", "director",
        "head", "vp", "vice president", "president", "avp", "evp", "svp", "founding", "chief",
        "architect", "expert", "distinguished", "lead engineer", "senior engineer",
        "senior developer", "tech lead", "team lead"
    ]

    filtered_jobs = []
    for job in all_jobs:
        t = " " + job.get("title", "").lower() + " "   # pad with spaces for boundary matching
        jd = job.get("jd_text", "").lower()

        if max_years is None:
            filtered_jobs.append(job)
            continue

        exclude = False
        min_exp_threshold = max_years + 1

        # Check non-tech exclusions
        if any(ex in t for ex in NON_TECH_EXCLUSIONS):
            exclude = True

        # Check senior title exclusions
        if not exclude and max_years <= 2 and any(ex in t for ex in SENIOR_EXCLUSIONS):
            exclude = True

        # Check Level 2+ designations (Software Engineer II, SDET III, SDE 2, Level 2+)
        if not exclude and max_years <= 2:
            designation_match = re.search(r"\b(ii|iii|iv|v|vi|2|3|4|5|6|7)\b", t)
            if designation_match:
                exclude = True

        # Check title for experience numbers (digits and English words)
        if not exclude:
            title_exp_match = re.search(r"\b([1-9]|\d{2})\s*(?:\+|[–—\-\+]\s*\d+)?\s*(?:to\s*\d+)?\s*(?:years?|yrs?|yr)\b", t)
            if title_exp_match:
                exp_val = int(title_exp_match.group(1))
                if exp_val >= min_exp_threshold:
                    exclude = True

            word_map = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}
            title_word_match = re.findall(r"\b(one|two|three|four|five|six|seven|eight|nine|ten)\s*(?:\+|[–—\-\+]\s*(?:one|two|three|four|five|six|seven|eight|nine|ten))?\s*(?:to\s*(?:one|two|three|four|five|six|seven|eight|nine|ten))?\s*(?:years?|yrs?|yr)\b", t)
            for w in title_word_match:
                if word_map.get(w, 0) >= min_exp_threshold:
                    exclude = True

        # Check JD text for experience requirements (digits and English words)
        if not exclude and jd:
            exp_patterns = [
                r"\b([1-9]|\d{2})\s*(?:\+|[–—\-\+]\s*\d+)?\s*(?:to\s*\d+)?\s*(?:years?|yrs?|yr)\b",
                r"\b(?:experience|exp)\s*:\s*([1-9]|\d{2})\b",
                r"\b(?:minimum|at\s+least|min|with)?\s*([1-9]|\d{2})\s*(?:\+|[–—\-\+]\s*\d+)?\s*(?:to\s*\d+)?\s*(?:years?|yrs?|yr)\b"
            ]
            for pat in exp_patterns:
                matches = re.findall(pat, jd)
                for m in matches:
                    try:
                        exp_val = int(m)
                        if exp_val >= min_exp_threshold:
                            exclude = True
                            break
                    except ValueError:
                        pass
                if exclude:
                    break

            if not exclude:
                word_matches = re.findall(r"\b(one|two|three|four|five|six|seven|eight|nine|ten)\s*(?:\+|[–—\-\+]\s*(?:one|two|three|four|five|six|seven|eight|nine|ten))?\s*(?:to\s*(?:one|two|three|four|five|six|seven|eight|nine|ten))?\s*(?:years?|yrs?|yr)\b", jd)
                word_map = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}
                for w in word_matches:
                    if word_map.get(w, 0) >= min_exp_threshold:
                        exclude = True



        if not exclude:
            filtered_jobs.append(job)

    # Filter by location to ensure we drop US jobs returned by Indeed for Indian searches
    final_jobs = []
    loc_lower = location.lower()
    base_loc = loc_lower.replace("remote", "").strip() if "remote" in loc_lower else loc_lower
    ind_cities = [
        "bengaluru", "bangalore", "mumbai", "delhi", "noida", "gurugram",
        "gurgaon", "hyderabad", "chennai", "pune", "india", "kolkata",
        "ahmedabad", "jaipur", "lucknow", "kochi", "thiruvananthapuram",
        "indore", "chandigarh", "coimbatore", "nagpur", "visakhapatnam",
    ]
    # Indian state abbreviations used by Indeed/jobspy (e.g. "KA, IN", "MH, IN")
    ind_state_codes = [
        "ka", "mh", "dl", "tn", "ts", "hr", "up", "rj", "gj", "wb",
        "ap", "kl", "mp", "pb", "or", "br", "jh", "ct", "ga",
    ]

    for job in filtered_jobs:
        job_loc = job.get("location", "").lower()
        if not job_loc or base_loc == "any" or base_loc == "worldwide":
            final_jobs.append(job)
            continue
            
        if base_loc == "india" or any(c in base_loc for c in ind_cities):
            # Strict India filter: job MUST mention India/Indian city — bare "Remote" is NOT enough
            has_india = (
                "india" in job_loc
                or any(c in job_loc for c in ind_cities)
                or ", in" in job_loc  # Country code format: "KA, IN"
                or any(job_loc.strip().startswith(sc + ",") for sc in ind_state_codes)
            )
            if has_india:
                final_jobs.append(job)
        else:
            loc_match = base_loc in job_loc or "anywhere" in job_loc
            if loc_match:
                final_jobs.append(job)

    # Shuffle so sources are interleaved in DB
    random.shuffle(final_jobs)

    print(f"[job_sources] Total unique jobs fetched: {len(final_jobs)} from {len(results)} sources (after exp & loc filter)")
    for name, r in results.items():
        print(f"  {name}: {len(r.jobs)} jobs" + (f" | errors: {r.errors}" if r.errors else ""))

    return SourceResult(jobs=final_jobs, errors=all_errors)


# Legacy compatibility
def fetch_jobs_from_enabled_sources() -> SourceResult:
    return fetch_jobs_from_all_sources()
