"""
linkedin_hr_scout.py — Scout recent LinkedIn HR/Recruiter hiring posts & Google Forms.

Features:
1. Searches recent recruiter/HR hiring posts posted within the last 3-7 days.
2. Extracts direct Google Form / Typeform application URLs (forms.gle, docs.google.com/forms).
3. Extracts recruiter contact email addresses if present.
4. Verifies mentioned companies against local ATS/custom company database.
"""

import logging
import re
from typing import Any, List, Dict
try:
    from agents.state import JobLead
except ImportError:
    JobLead = Dict[str, Any]
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from services.db import get_conn

logger = logging.getLogger(__name__)

# Regular expressions for direct forms and recruiter emails
GOOGLE_FORM_REGEX = re.compile(
    r'https?://(?:forms\.gle|docs\.google\.com/forms|typeform\.com/to|airtable\.com/app)[^\s"\'<>)]+',
    re.IGNORECASE
)

EMAIL_REGEX = re.compile(
    r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
)


def _verify_company_has_careers(company_name: str) -> Dict[str, Any] | None:
    """Verify if a company exists in our database with active jobs or career pages."""
    if not company_name or len(company_name) < 2:
        return None

    c_name = company_name.lower().strip()
    with get_conn() as conn:
        # Check ats_companies
        row = conn.execute(
            "SELECT name, ats_type, token FROM ats_companies WHERE lower(name) LIKE ? AND status != 'invalid' LIMIT 1",
            (f"%{c_name}%",)
        ).fetchone()

        if row:
            return {
                "name": row["name"],
                "ats_type": row["ats_type"],
                "token": row["token"],
                "is_verified": True
            }

        # Check companies_custom
        row2 = conn.execute(
            "SELECT name, career_url FROM companies_custom WHERE lower(name) LIKE ? AND status = 'active' LIMIT 1",
            (f"%{c_name}%",)
        ).fetchone()

        if row2:
            return {
                "name": row2["name"],
                "career_url": row2["career_url"],
                "is_verified": True
            }

    return None


def fetch_linkedin_hr_posts(keyword: str, location: str, max_results: int = 15) -> List[JobLead]:
    """
    Search for recent recruiter/HR hiring posts and Google Form applications posted within 3-7 days.
    """
    from ddgs import DDGS

    jobs: List[JobLead] = []
    seen_urls: set[str] = set()

    # Build search queries targeting hiring posts & Google Forms
    first_kw = keyword.split(",")[0].strip() if keyword else "Software Engineer"
    loc = location.split(",")[0].strip() if location else "India"

    search_queries = [
        f'"{first_kw}" "{loc}" "hiring" (forms.gle OR "google.com/forms")',
        f'"{first_kw}" "{loc}" "we are hiring" "apply"',
        f'"{first_kw}" "{loc}" "hiring" "send resume"',
        f'"{first_kw}" "{loc}" "recruiter" "opening"',
    ]

    ddgs = DDGS()

    for q in search_queries:
        if len(jobs) >= max_results:
            break

        try:
            results = list(ddgs.text(q, timelimit="w", max_results=10))
            for r in results:
                title = r.get("title", "").strip()
                snippet = r.get("body", "").strip()
                post_url = r.get("href", "").strip()

                if not title or not post_url or post_url in seen_urls:
                    continue

                full_text = f"{title} {snippet}"

                # 1. Detect Direct Google Form / Typeform link
                gform_match = GOOGLE_FORM_REGEX.search(full_text)
                apply_url = gform_match.group(0) if gform_match else post_url

                # 2. Detect Recruiter Email
                email_match = EMAIL_REGEX.search(full_text)
                recruiter_email = email_match.group(0) if email_match else None

                # 3. Extract Company Name if present in title/snippet
                company_name = "LinkedIn HR Hiring Post"
                company_match = re.search(r'(?:at|@|hiring for)\s+([A-Z][A-Za-z0-9\s\.]{2,20})', full_text, re.IGNORECASE)
                if company_match:
                    raw_cname = company_match.group(1).strip()
                    # Filter out noise
                    if raw_cname.lower() not in ("us", "india", "remote", "full time", "part time", "urgent", "immediate"):
                        company_name = raw_cname

                # Verify if company has known career portal
                verified_info = _verify_company_has_careers(company_name)
                is_verified = verified_info is not None

                source_tag = "hr_google_form" if gform_match else "hr_post"

                seen_urls.add(post_url)
                if apply_url != post_url:
                    seen_urls.add(apply_url)

                job_lead: JobLead = {
                    "company": verified_info["name"] if is_verified else company_name,
                    "title": title[:100],
                    "location": loc,
                    "url": apply_url,
                    "jd_text": f"{snippet}\n\n[Recruiter Email: {recruiter_email}]" if recruiter_email else snippet,
                    "source": source_tag,
                }
                jobs.append(job_lead)

                if len(jobs) >= max_results:
                    break

        except Exception as e:
            logger.debug(f"[linkedin_hr_scout] DDGS query failed: {e}")

    logger.info(f"[linkedin_hr_scout] Discovered {len(jobs)} recent HR posts & Google Forms")
    return jobs


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    posts = fetch_linkedin_hr_posts("Software Engineer", "India", max_results=10)
    print(f"\nTotal HR Posts Found: {len(posts)}")
    for p in posts:
        print(f"  [{p['source']}] {p['company']} - {p['title']}")
        print(f"     URL: {p['url']}")
        print()
