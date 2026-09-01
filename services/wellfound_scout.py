"""
wellfound_scout.py — Scout startup jobs from Wellfound (formerly AngelList Talent) & YC WorkAtAStartup.

Fetches early-stage, Series A, Series B, and high-growth startup roles.
"""

import logging
import re
from typing import Any, Dict, List
from ddgs import DDGS

try:
    from agents.state import JobLead
except ImportError:
    JobLead = Dict[str, Any]

logger = logging.getLogger(__name__)


def fetch_wellfound_jobs(keyword: str, location: str, max_results: int = 20) -> List[JobLead]:
    """Fetch startup jobs from Wellfound (AngelList) and YC WorkAtAStartup."""
    jobs: List[JobLead] = []
    seen_urls: set[str] = set()

    first_kw = keyword.split(",")[0].strip() if keyword else "Software Engineer"
    loc = location.split(",")[0].strip() if location else "India"

    search_queries = [
        f'"wellfound.com" "{first_kw}" "{loc}"',
        f'"wellfound.com/jobs" "{first_kw}" "{loc}"',
        f'"wellfound.com/role" "{first_kw}" "{loc}"',
        f'"workatastartup.com" "{first_kw}" "{loc}"',
    ]

    ddgs = DDGS()

    for q in search_queries:
        if len(jobs) >= max_results:
            break

        try:
            results = list(ddgs.text(q, max_results=15))
            for r in results:
                title = r.get("title", "").strip()
                snippet = r.get("body", "").strip()
                url = r.get("href", "").strip()

                if not title or not url or url in seen_urls:
                    continue

                # Filter out generic listing index pages
                if url in ("https://wellfound.com/", "https://wellfound.com/location/india", "https://wellfound.com/jobs"):
                    continue

                # Extract company name from Wellfound title (e.g. "Software Engineer at Vested Finance • India")
                company_name = "Wellfound Startup"
                c_match = re.search(r'(?:at|@)\s+([A-Za-z0-9\s\.]{2,25})(?:\s*•|\s*-|\s*\|)', title, re.IGNORECASE)
                if c_match:
                    company_name = c_match.group(1).strip()
                elif " - " in title:
                    company_name = title.split(" - ")[0].strip()

                # Clean up title
                clean_title = title.replace(" | Wellfound", "").replace(" • Wellfound", "").strip()

                seen_urls.add(url)
                jobs.append({
                    "company": company_name,
                    "title": clean_title[:100],
                    "location": loc,
                    "url": url,
                    "jd_text": snippet,
                    "source": "wellfound",
                })

                if len(jobs) >= max_results:
                    break
        except Exception as e:
            logger.debug(f"[wellfound_scout] DDGS query failed: {e}")

    logger.info(f"[wellfound_scout] Discovered {len(jobs)} startup jobs from Wellfound & YC")
    return jobs


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    res = fetch_wellfound_jobs("Software Engineer", "India", max_results=10)
    print(f"\nTotal Wellfound Jobs: {len(res)}")
    for j in res:
        print(f"  [{j['source']}] {j['company']} - {j['title']} -> {j['url']}")
