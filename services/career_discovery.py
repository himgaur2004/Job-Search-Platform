"""
career_discovery.py — Discover career page URLs for companies in companies_custom.

For each company:
1. Probe common career page paths (HEAD/GET requests)
2. If found, check if it embeds a known ATS (Greenhouse, Lever, etc.)
3. If ATS detected → move to ats_companies
4. If custom career page → store career_url for browser crawling
"""

import logging
import os
import re
import sqlite3
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse

import requests

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from services.db import get_conn

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml",
}

# Common career page paths to probe
CAREER_PATHS = [
    "/careers",
    "/jobs",
    "/join-us",
    "/work-with-us",
    "/career",
    "/hiring",
    "/openings",
    "/join",
    "/team",
    "/about/careers",
    "/company/careers",
    "/en/careers",
    "/life",
    "/work",
    "/opportunities",
]

# ATS detection patterns in HTML content
ATS_PATTERNS = {
    "greenhouse": [
        r"boards\.greenhouse\.io/(\w+)",
        r"greenhouse\.io/embed/job_board",
        r"grnh\.se",
    ],
    "lever": [
        r"jobs\.lever\.co/(\w[\w-]*)",
        r"lever\.co/(\w[\w-]*)",
    ],
    "ashby": [
        r"jobs\.ashbyhq\.com/(\w[\w-]*)",
        r"ashbyhq\.com",
    ],
    "workable": [
        r"apply\.workable\.com/(\w[\w-]*)",
        r"workable\.com",
    ],
    "bamboohr": [
        r"(\w+)\.bamboohr\.com/careers",
    ],
    "workday": [
        r"(\w+)\.wd\d\.myworkdayjobs\.com",
        r"myworkdayjobs\.com",
    ],
    "icims": [
        r"careers-?\w*\.icims\.com",
        r"icims\.com",
    ],
    "smartrecruiters": [
        r"careers\.smartrecruiters\.com",
        r"smartrecruiters\.com",
    ],
    "recruitee": [
        r"(\w+)\.recruitee\.com",
    ],
    "teamtailor": [
        r"(\w+)\.teamtailor\.com",
        r"career\.(\w+)\.com.*teamtailor",
    ],
}


def _detect_ats_in_html(html: str) -> tuple[str, str] | None:
    """Check if HTML contains references to a known ATS. Returns (ats_type, token) or None."""
    for ats_type, patterns in ATS_PATTERNS.items():
        for pattern in patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                token = match.group(1) if match.lastindex else ""
                return ats_type, token
    return None


def _probe_company(company: dict) -> dict:
    """
    Probe a single company's domain for career pages.
    Returns a result dict with status, career_url, and optionally ats info.
    """
    name = company["name"]
    domain = company["domain"]
    result = {
        "id": company["id"],
        "name": name,
        "domain": domain,
        "status": "no_careers",
        "career_url": None,
        "ats_type": None,
        "ats_token": None,
    }

    base_urls = [f"https://{domain}", f"https://www.{domain}"]

    for base_url in base_urls:
        for path in CAREER_PATHS:
            url = f"{base_url}{path}"
            try:
                resp = requests.get(url, timeout=5, headers=HEADERS, allow_redirects=True)
                if resp.status_code == 200 and len(resp.text) > 500:
                    # Check for ATS in the HTML
                    ats_result = _detect_ats_in_html(resp.text)
                    if ats_result:
                        ats_type, token = ats_result
                        result["status"] = "ats_detected"
                        result["career_url"] = str(resp.url)
                        result["ats_type"] = ats_type
                        result["ats_token"] = token or domain.split(".")[0]
                        logger.info(f"  ✓ {name} → {ats_type} detected at {path}")
                        return result

                    # Check if the page actually looks like a career page
                    text_lower = resp.text.lower()
                    career_indicators = [
                        "job opening", "open position", "career",
                        "join our team", "we're hiring", "apply now",
                        "current opening", "job listing", "work with us",
                        "open role", "view position",
                    ]
                    if any(indicator in text_lower for indicator in career_indicators):
                        result["status"] = "active"
                        result["career_url"] = str(resp.url)
                        logger.info(f"  ○ {name} → custom career page at {path}")
                        return result

            except requests.RequestException:
                continue

    logger.info(f"  ✗ {name} → no career page found")
    return result


def discover_career_pages(batch_size: int = 50, max_workers: int = 10) -> dict:
    """
    Discover career pages for all pending companies in companies_custom.
    Returns stats dict.
    """
    from datetime import datetime, timezone

    with get_conn() as conn:
        companies = conn.execute(
            """
            SELECT id, name, domain 
            FROM companies_custom 
            WHERE status = 'pending'
            LIMIT ?
            """,
            (batch_size,),
        ).fetchall()
        companies = [dict(c) for c in companies]

    if not companies:
        logger.info("[career_discovery] No pending companies to process.")
        return {"processed": 0}

    logger.info(f"[career_discovery] Probing {len(companies)} companies for career pages...")

    stats = {"processed": 0, "active": 0, "ats_detected": 0, "no_careers": 0, "errors": 0}
    now = datetime.now(timezone.utc).isoformat()

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_probe_company, c): c for c in companies}

        try:
            for future in as_completed(futures, timeout=300):
                try:
                    result = future.result()
                    stats["processed"] += 1

                    with get_conn() as conn:
                        if result["status"] == "ats_detected":
                            stats["ats_detected"] += 1
                            try:
                                conn.execute(
                                    "INSERT OR IGNORE INTO ats_companies (name, ats_type, token) VALUES (?, ?, ?)",
                                    (result["name"], result["ats_type"], result["ats_token"]),
                                )
                            except sqlite3.Error:
                                pass
                            conn.execute(
                                "UPDATE companies_custom SET status=?, career_url=?, ats_detected=?, last_checked=? WHERE id=?",
                                (result["status"], result["career_url"], result["ats_type"], now, result["id"]),
                            )

                        elif result["status"] == "active":
                            stats["active"] += 1
                            conn.execute(
                                "UPDATE companies_custom SET status=?, career_url=?, last_checked=? WHERE id=?",
                                ("active", result["career_url"], now, result["id"]),
                            )

                        else:
                            stats["no_careers"] += 1
                            conn.execute(
                                "UPDATE companies_custom SET status=?, last_checked=? WHERE id=?",
                                ("no_careers", now, result["id"]),
                            )

                except Exception as e:
                    stats["errors"] += 1
                    logger.error(f"  Error processing company: {e}")
        except TimeoutError:
            logger.warning("[career_discovery] Timeout reached for remaining companies.")

    logger.info(
        f"[career_discovery] Done: {stats['processed']} processed, "
        f"{stats['active']} active, {stats['ats_detected']} ATS detected, "
        f"{stats['no_careers']} no careers"
    )
    return stats


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    stats = discover_career_pages(batch_size=250, max_workers=15)
    print(f"\nResults: {stats}")
