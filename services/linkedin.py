from __future__ import annotations

import os
import time
import random
import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Any

# LinkedIn public guest API – no auth needed, no bot detection
_GUEST_JOBS_URL = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.linkedin.com/jobs/search/",
}


def search_jobs(keyword: str, location: str, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Scrapes LinkedIn jobs using their public guest API endpoint.
    No authentication required – avoids bot detection entirely.
    """
    results = []
    start = 0
    batch = 25  # LinkedIn returns up to 25 per page

    while len(results) < limit:
        params = {
            "keywords": keyword,
            "location": location,
            "start": start,
            "count": batch,
        }
        try:
            resp = requests.get(
                _GUEST_JOBS_URL,
                params=params,
                headers=_HEADERS,
                timeout=20,
            )
            resp.raise_for_status()
        except requests.RequestException as e:
            print(f"LinkedIn guest API error: {e}")
            break

        soup = BeautifulSoup(resp.text, "html.parser")
        cards = soup.find_all("li")

        if not cards:
            break  # No more results

        for card in cards:
            # Extract job ID & build clean URL
            job_id_tag = card.find("div", {"data-entity-urn": True})
            job_id = ""
            if job_id_tag:
                urn = job_id_tag.get("data-entity-urn", "")
                job_id = urn.split(":")[-1]

            # Title
            title_tag = card.find("h3", class_="base-search-card__title")
            title = title_tag.get_text(strip=True) if title_tag else ""

            # Company
            company_tag = card.find("h4", class_="base-search-card__subtitle")
            company = company_tag.get_text(strip=True) if company_tag else ""

            # Location
            location_tag = card.find("span", class_="job-search-card__location")
            job_location = location_tag.get_text(strip=True) if location_tag else location

            # URL (prefer canonical link)
            link_tag = card.find("a", class_="base-card__full-link")
            url = link_tag.get("href", "").split("?")[0] if link_tag else (
                f"https://www.linkedin.com/jobs/view/{job_id}/" if job_id else ""
            )

            if title and company and url:
                results.append({
                    "title": title,
                    "company": company,
                    "location": job_location,
                    "url": url,
                    "source": "linkedin",
                })

            if len(results) >= limit:
                break

        start += batch
        # Polite delay between pages
        time.sleep(random.uniform(1.0, 2.5))

    # Deduplicate by URL
    seen: set = set()
    unique = []
    for r in results:
        if r["url"] not in seen:
            seen.add(r["url"])
            unique.append(r)

    print(f"LinkedIn guest API: extracted {len(unique)} unique jobs for '{keyword}' in '{location}'")
    return unique[:limit]


def search_posts_by_hashtag(hashtag: str = "sde", limit: int = 5) -> List[Dict[str, Any]]:
    """Stub – hashtag post scraping not supported via guest API."""
    return []


def find_company_contacts(company_name: str) -> List[Dict[str, str]]:
    """Stub – contact discovery requires separate implementation."""
    return [
        {"name": "Jane Doe", "title": "Technical Recruiter", "profile_url": "https://linkedin.com/in/stub"},
        {"name": "John Smith", "title": "Senior Software Engineer", "profile_url": "https://linkedin.com/in/stub"},
    ]
