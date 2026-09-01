"""
sync_crawler_jobs_to_dashboard.py — Ultra-strict Software Engineering Entry-Level (0-2 Yrs) & India-Only Filter.
"""

import logging
import os
import re
import sys
from typing import Dict, List, Set

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from services.db import get_conn, upsert_job

logger = logging.getLogger(__name__)

# Must match at least one of these core tech engineering keywords
TECH_TITLE_INCLUSIONS = [
    "software", "developer", "sde", "frontend", "front-end", "backend", "back-end",
    "fullstack", "full-stack", "full stack", "data engineer", "machine learning",
    "ml engineer", "ai engineer", "devops", "cloud engineer", "qa engineer",
    "automation engineer", "systems engineer", "site reliability", "sre", "web developer",
    "python developer", "java developer", "react developer", "node developer",
    "golang developer", "sdet", "test engineer",
    "software intern", "software trainee", "developer intern", "sde intern",
    "ios developer", "android developer", "mobile developer", "data scientist",
    "research engineer", "applied scientist", "deep learning", "nlp engineer",
    "computer vision", "blockchain developer",
]


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

# Seniority titles to strictly EXCLUDE for 0-2 yrs experience candidates
SENIOR_EXCLUSIONS = [
    "senior", "sr.", "sr ", "staff", "lead", "principal", "principle", "manager", "director",
    "head", "vp", "vice president", "president", "avp", "evp", "svp", "founding", "chief",
    "architect", "expert", "distinguished", "lead engineer", "senior engineer",
    "senior developer", "tech lead", "team lead"
]

# Foreign countries/cities to strictly EXCLUDE
FOREIGN_EXCLUSIONS = [
    "united states", "usa", ", us", "uk,", "united kingdom", "london", "germany",
    "berlin", "ireland", "dublin", "australia", "sydney", "canada", "toronto",
    "singapore", "brazil", "poland", "lithuania", "serbia", "bulgaria", "japan",
    "tokyo", "france", "paris", "netherlands", "amsterdam", "spain", "madrid",
    "new york", "san francisco", "seattle", "chicago", "boston", "denver",
    "austin", "portland", "los angeles", "washington", "mexico", "bellevue",
    ", wa", ", ca", ", ny", ", tx", ", il", ", co", ", or", ", fl", ", ma",
    ", dc", ", ga", ", nc", ", va", ", mi", ", oh", ", pa", ", mn", ", az",
    "emea", "apac", "latam", "europe", "ukraine", "israel", "vietnam", "philippines",
    "illinois", "california", "texas", "georgia", "florida", "ohio", "michigan",
    "colorado", "minnesota", "arizona", "oregon", "virginia", "pennsylvania",
    "massachusetts", "connecticut", "maryland", "new jersey", "tennessee",
    "north carolina", "south carolina", "utah", "wisconsin", "indiana",
    "midwest", "northeast", "southeast", "west coast", "east coast",
    "saudi", "riyadh", "dubai", "qatar", "doha", "abu dhabi",
    "south africa", "kenya", "nigeria", "egypt", "colombia", "argentina",
]

INDIAN_LOCATIONS = [
    "bengaluru", "bangalore", "noida", "gurugram", "gurgaon", "mumbai", "pune",
    "hyderabad", "chennai", "delhi", "kolkata", "ahmedabad", "jaipur", "lucknow",
    "kochi", "thiruvananthapuram", "indore", "chandigarh", "coimbatore", "india",
    "ncr", "greater delhi", "nagpur", "bhubaneswar"
]


def is_strict_software_entry_level_india(title: str, location: str, jd_text: str, max_years: int = 0) -> bool:
    t_lower = title.lower()
    l_lower = location.lower()
    jd_lower = (jd_text or "").lower()

    # 1. Must be a Core Tech / Software Engineering Role
    is_tech = any(inc in t_lower for inc in TECH_TITLE_INCLUSIONS)
    if not is_tech:
        return False

    # 2. Exclude Non-Tech & Support Roles
    for ex in NON_TECH_EXCLUSIONS:
        if ex in t_lower:
            return False

    # 3. Exclude Seniority (Staff, Sr, Lead, Principal, Vice President, etc.)
    for ex in SENIOR_EXCLUSIONS:
        if ex in t_lower:
            return False

    # 3b. Exclude Level 2+ designations like II, III, IV, V, VI, 2, 3, 4, 5 in title
    designation_match = re.search(r"\b(ii|iii|iv|v|vi|2|3|4|5|6|7)\b", t_lower)
    if designation_match:
        return False

    # 4. Strict India-ONLY Location Filter
    # First check explicit foreign markers
    if any(foreign in l_lower for foreign in FOREIGN_EXCLUSIONS):
        return False

    # Must explicitly mention an Indian city/state/country OR "remote" with "india"
    has_india_keyword = any(ind in l_lower for ind in INDIAN_LOCATIONS if ind != "india") or bool(re.search(r"\bindia\b", l_lower))
    is_remote_india = "remote" in l_lower and has_india_keyword
    is_india = has_india_keyword or is_remote_india
    if not is_india:
        return False

    # 5. Strict Experience Filter based on max_years
    min_exp_threshold = max_years + 1

    # Check title for experience numbers in digits or words
    title_exp_match = re.search(r"\b([1-9]|\d{2})\s*(?:\+|[–—\-\+]\s*\d+)?\s*(?:to\s*\d+)?\s*(?:years?|yrs?|yr)\b", t_lower)
    if title_exp_match:
        exp_val = int(title_exp_match.group(1))
        if exp_val >= min_exp_threshold:
            return False

    title_word_match = re.findall(r"\b(one|two|three|four|five|six|seven|eight|nine|ten)\s*(?:\+|[–—\-\+]\s*(?:one|two|three|four|five|six|seven|eight|nine|ten))?\s*(?:to\s*(?:one|two|three|four|five|six|seven|eight|nine|ten))?\s*(?:years?|yrs?|yr)\b", t_lower)
    word_map = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}
    for w in title_word_match:
        if word_map.get(w, 0) >= min_exp_threshold:
            return False

    # Check JD for experience requirements (digits and English words)
    exp_patterns = [
        r"\b([1-9]|\d{2})\s*(?:\+|[–—\-\+]\s*\d+)?\s*(?:to\s*\d+)?\s*(?:years?|yrs?|yr)\b",
        r"\b(?:experience|exp)\s*:\s*([1-9]|\d{2})\b",
        r"\b(?:minimum|at\s+least|min|with)?\s*([1-9]|\d{2})\s*(?:\+|[–—\-\+]\s*\d+)?\s*(?:to\s*\d+)?\s*(?:years?|yrs?|yr)\b"
    ]
    for pat in exp_patterns:
        matches = re.findall(pat, jd_lower)
        for m in matches:
            try:
                exp_val = int(m)
                if exp_val >= min_exp_threshold:
                    return False
            except ValueError:
                pass

    # Check for English word experience numbers (e.g. "three years", "two to four years")
    word_matches = re.findall(r"\b(one|two|three|four|five|six|seven|eight|nine|ten)\s*(?:\+|[–—\-\+]\s*(?:one|two|three|four|five|six|seven|eight|nine|ten))?\s*(?:to\s*(?:one|two|three|four|five|six|seven|eight|nine|ten))?\s*(?:years?|yrs?|yr)\b", jd_lower)
    for w in word_matches:
        if word_map.get(w, 0) >= min_exp_threshold:
            return False



    return True


def sync_jobs_to_dashboard(max_jobs: int = 500, max_years: int = 0):
    import asyncio
    from services.jd_fetcher import batch_fetch_missing_jds

    with get_conn() as conn:
        conn.execute("DELETE FROM jobs")
        conn.commit()

        # Build company_id -> name map
        company_rows = conn.execute("SELECT id, name FROM ats_companies").fetchall()
        company_map = {r["id"]: r["name"] for r in company_rows}

        # Build set of company_ids that belong to CSV-ingested startups
        csv_startup_company_ids: Set[int] = set()
        csv_domains = conn.execute("SELECT domain FROM companies_custom WHERE status = 'active'").fetchall()
        csv_tokens = set()
        for r in csv_domains:
            domain = r["domain"]
            token = domain.split(".")[0].lower()
            csv_tokens.add(token)
            csv_tokens.add(domain.replace(".", "").lower())

        for cid, cname in company_map.items():
            cname_lower = cname.lower() if cname else ""
            if cname_lower in csv_tokens or any(tok in cname_lower for tok in csv_tokens if len(tok) >= 4):
                csv_startup_company_ids.add(cid)

        # ──── PASS 1: CSV Startup Jobs (Priority) ────
        startup_query = """
        SELECT company_id, title, location, url, jd_text, source, last_seen
        FROM ats_crawler_jobs
        WHERE company_id IN ({})
        ORDER BY last_seen DESC
        """.format(",".join(str(cid) for cid in csv_startup_company_ids) if csv_startup_company_ids else "0")
        
        startup_rows = [dict(r) for r in conn.execute(startup_query).fetchall()]

        # ──── PASS 2: All Other Jobs ────
        general_query = """
        SELECT company_id, title, location, url, jd_text, source, last_seen
        FROM ats_crawler_jobs
        ORDER BY last_seen DESC
        """
        general_rows = [dict(r) for r in conn.execute(general_query).fetchall()]

    print(f"Scanning {len(startup_rows)} CSV startup jobs + {len(general_rows)} general jobs with max_years={max_years}...")

    synced = 0
    synced_urls: Set[str] = set()

    # Pass 1: CSV Startup priority jobs
    candidate_startups = [
        r for r in startup_rows 
        if any(inc in r["title"].lower() for inc in TECH_TITLE_INCLUSIONS)
        and not any(ex in r["title"].lower() for ex in NON_TECH_EXCLUSIONS)
        and not any(ex in r["title"].lower() for ex in SENIOR_EXCLUSIONS)
    ]
    # Fetch missing JDs on-the-fly for candidate startup jobs (top 300)
    candidate_startups = asyncio.run(batch_fetch_missing_jds(candidate_startups[:300]))

    verified_jobs = []

    for r in candidate_startups:
        if len(verified_jobs) >= max_jobs:
            break
        title = r["title"]
        location = r["location"] or "India"
        jd_text = r["jd_text"] or ""
        company_name = company_map.get(r["company_id"]) or "Tech Startup"
        url = r["url"]
        source = r["source"] or "ats_crawler"

        if url in synced_urls:
            continue

        if is_strict_software_entry_level_india(title, location, jd_text, max_years=max_years):
            job_dict = {
                "company": company_name,
                "title": title,
                "location": location,
                "url": url,
                "jd_text": jd_text,
                "source": source,
            }
            verified_jobs.append((job_dict, 99.0))
            synced_urls.add(url)

    # Pass 2: General jobs
    candidate_general = [
        r for r in general_rows 
        if any(inc in r["title"].lower() for inc in TECH_TITLE_INCLUSIONS)
        and not any(ex in r["title"].lower() for ex in NON_TECH_EXCLUSIONS)
        and not any(ex in r["title"].lower() for ex in SENIOR_EXCLUSIONS)
        and r["url"] not in synced_urls
    ]
    # Fetch missing JDs on-the-fly for candidate general jobs (top 15000)
    candidate_general = asyncio.run(batch_fetch_missing_jds(candidate_general[:15000]))

    for r in candidate_general:
        if len(verified_jobs) >= max_jobs:
            break
        title = r["title"]
        location = r["location"] or "India"
        jd_text = r["jd_text"] or ""
        company_name = company_map.get(r["company_id"]) or "Tech Startup"
        url = r["url"]
        source = r["source"] or "ats_crawler"

        if url in synced_urls:
            continue

        if is_strict_software_entry_level_india(title, location, jd_text, max_years=max_years):
            job_dict = {
                "company": company_name,
                "title": title,
                "location": location,
                "url": url,
                "jd_text": jd_text,
                "source": source,
            }
            verified_jobs.append((job_dict, 96.0))
            synced_urls.add(url)

    # Atomic database update: clear old jobs and insert newly verified jobs in a single transaction
    with get_conn() as conn:
        conn.execute("DELETE FROM jobs")
        conn.commit()

    synced = 0
    for job_dict, score in verified_jobs:
        try:
            upsert_job(job_dict, match_score=score)
            synced += 1
        except Exception as e:
            logger.debug(f"Sync error for {job_dict.get('url')}: {e}")

    print(f"\nTotal synced {synced} Entry-Level Software Engineering (max_years={max_years}) India Jobs into Dashboard!")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    sync_jobs_to_dashboard(max_years=0)
