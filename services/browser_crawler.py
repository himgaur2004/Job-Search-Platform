"""
browser_crawler.py — Crawl custom career pages using Playwright.

For companies that have a career_url but no known ATS,
this module renders the page in a headless browser to handle:
- JavaScript-rendered content (React, Vue, Angular)
- Dynamic job listings
- Pagination
- Accordion/expandable sections

Returns the rendered HTML for LLM extraction.
"""

import logging
import os
import sys
import time
from typing import Optional

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from services.db import get_conn

logger = logging.getLogger(__name__)


def crawl_career_page(url: str, timeout_ms: int = 15000) -> Optional[str]:
    """
    Render a career page using Playwright and return the DOM HTML.
    Returns None if the page fails to load or has no meaningful content.
    """
    from playwright.sync_api import sync_playwright

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1280, "height": 720},
            )
            page = context.new_page()

            # Navigate and wait for network to settle
            page.goto(url, wait_until="networkidle", timeout=timeout_ms)

            # Wait a bit for any lazy-loaded content
            page.wait_for_timeout(2000)

            # Try clicking common "View All Jobs" / "Load More" buttons
            load_more_selectors = [
                "button:has-text('Load More')",
                "button:has-text('View All')",
                "button:has-text('Show More')",
                "a:has-text('View All Jobs')",
                "a:has-text('See All')",
                "button:has-text('See all')",
            ]
            for selector in load_more_selectors:
                try:
                    btn = page.locator(selector).first
                    if btn.is_visible(timeout=1000):
                        btn.click()
                        page.wait_for_timeout(2000)
                        break
                except Exception:
                    continue

            # Get the rendered HTML
            html = page.content()

            browser.close()

            if len(html) < 500:
                logger.warning(f"[browser_crawler] Page too small ({len(html)} bytes): {url}")
                return None

            return html

    except Exception as e:
        logger.error(f"[browser_crawler] Failed to crawl {url}: {e}")
        return None


def crawl_active_companies(batch_size: int = 20) -> list[dict]:
    """
    Crawl all 'active' companies in companies_custom that have a career_url.
    Returns list of {company_id, name, domain, career_url, html} dicts.
    """
    with get_conn() as conn:
        companies = conn.execute(
            """
            SELECT id, name, domain, career_url
            FROM companies_custom
            WHERE status = 'active' AND career_url IS NOT NULL
            LIMIT ?
            """,
            (batch_size,),
        ).fetchall()
        companies = [dict(c) for c in companies]

    if not companies:
        logger.info("[browser_crawler] No active companies to crawl.")
        return []

    logger.info(f"[browser_crawler] Crawling {len(companies)} career pages...")

    results = []
    for i, company in enumerate(companies):
        logger.info(
            f"  [{i+1}/{len(companies)}] {company['name']} → {company['career_url']}"
        )

        html = crawl_career_page(company["career_url"])
        if html:
            results.append({
                "company_id": company["id"],
                "name": company["name"],
                "domain": company["domain"],
                "career_url": company["career_url"],
                "html": html,
            })

        # Rate limiting: 3 seconds between requests
        if i < len(companies) - 1:
            time.sleep(3)

    logger.info(f"[browser_crawler] Crawled {len(results)}/{len(companies)} pages successfully.")
    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    results = crawl_active_companies(batch_size=5)
    for r in results:
        print(f"  {r['name']}: {len(r['html'])} bytes of HTML")
