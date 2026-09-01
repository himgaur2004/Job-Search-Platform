"""
job_extractor.py — LLM-powered job extraction from career page HTML.

Takes raw HTML from browser_crawler and uses Groq (free tier) to extract
structured job listings. Falls back to regex-based extraction if LLM fails.
"""

import json
import logging
import os
import re
import sys
from typing import Any

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

logger = logging.getLogger(__name__)

# Maximum HTML size to send to LLM (tokens ≈ chars/4) to stay well under Groq 6000 TPM limit
MAX_HTML_CHARS = 5000


def _clean_html_for_llm(html: str) -> str:
    """Strip unnecessary HTML to reduce token usage."""
    # Remove script, style, svg, noscript, head, footer, nav, header, iframe, path, meta, link tags
    html = re.sub(r"<(script|style|svg|noscript|head|footer|nav|header|iframe|path|meta|link)[^>]*>.*?</\1>", "", html, flags=re.DOTALL | re.IGNORECASE)
    # Remove HTML comments
    html = re.sub(r"<!--.*?-->", "", html, flags=re.DOTALL)
    # Strip ALL tag attributes except href and id
    html = re.sub(r'\s+(?!href|id)[\w-]+=(?:"[^"]*"|\'[^\']*\'|[^\s>]+)', "", html)
    # Collapse whitespace
    html = re.sub(r"\s+", " ", html)
    # Remove empty tags
    html = re.sub(r"<(\w+)[^>]*>\s*</\1>", "", html)

    # Truncate if still too long
    if len(html) > MAX_HTML_CHARS:
        html = html[:MAX_HTML_CHARS] + "\n... [truncated]"

    return html.strip()


EXTRACTION_PROMPT = """You are a job listing extractor. Given the HTML of a company's careers page, extract every job posting you can find.

Return ONLY a valid JSON array. Each object must have these fields:
- "title": Job title (string)
- "location": Location or "Remote" (string)
- "apply_url": Direct URL to apply or view the job (string, must start with http)
- "department": Department if visible (string or null)

Rules:
- Only extract ACTUAL job postings, not blog posts or general info
- If you find a relative URL like "/careers/123", convert it to a full URL using the base domain: {base_url}
- If no jobs are found, return an empty array: []
- Do NOT include any explanation, only the JSON array

HTML:
{html}"""


def extract_jobs_with_llm(
    html: str, company_name: str, career_url: str
) -> list[dict[str, Any]]:
    """
    Use Groq LLM to extract structured job data from career page HTML.
    Returns a list of job dicts.
    """
    from dotenv import load_dotenv
    load_dotenv()

    groq_key = os.getenv("GROQ_API_KEY", "")
    if not groq_key:
        logger.warning("[job_extractor] No GROQ_API_KEY set, falling back to regex extraction")
        return extract_jobs_with_regex(html, career_url)

    # Clean HTML for LLM
    cleaned = _clean_html_for_llm(html)
    if len(cleaned) < 100:
        logger.warning(f"[job_extractor] HTML too short for {company_name}")
        return []

    # Build prompt
    from urllib.parse import urlparse
    parsed = urlparse(career_url)
    base_url = f"{parsed.scheme}://{parsed.netloc}"

    prompt = EXTRACTION_PROMPT.format(html=cleaned, base_url=base_url)

    try:
        import requests as req

        resp = req.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {groq_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": os.getenv("GROQ_MODEL", "llama-3.1-8b-instant"),
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0,
                "max_tokens": 4000,
            },
            timeout=30,
        )

        if resp.status_code == 200:
            data = resp.json()
            content = data["choices"][0]["message"]["content"]

            # Extract JSON from response (handle markdown code blocks)
            json_match = re.search(r"\[.*\]", content, re.DOTALL)
            if json_match:
                jobs = json.loads(json_match.group())
                if isinstance(jobs, list):
                    # Validate and normalize
                    valid_jobs = []
                    for j in jobs:
                        if not isinstance(j, dict):
                            continue
                        title = j.get("title", "").strip()
                        if not title:
                            continue

                        # Fix relative URLs
                        apply_url = j.get("apply_url", "")
                        if apply_url and not apply_url.startswith("http"):
                            apply_url = f"{base_url}{apply_url}" if apply_url.startswith("/") else f"{base_url}/{apply_url}"

                        valid_jobs.append({
                            "title": title,
                            "location": j.get("location", "Unknown"),
                            "url": apply_url or career_url,
                            "department": j.get("department"),
                            "jd_text": "",
                            "source": "custom_llm",
                        })

                    logger.info(
                        f"[job_extractor] LLM extracted {len(valid_jobs)} jobs from {company_name}"
                    )
                    return valid_jobs
            else:
                logger.warning(f"[job_extractor] No JSON found in LLM response for {company_name}")
        else:
            logger.error(
                f"[job_extractor] Groq API error {resp.status_code}: {resp.text[:200]}"
            )

    except Exception as e:
        logger.error(f"[job_extractor] LLM extraction failed for {company_name}: {e}")

    # Fallback to regex
    return extract_jobs_with_regex(html, career_url)


def extract_jobs_with_regex(html: str, career_url: str) -> list[dict[str, Any]]:
    """
    Fallback regex-based job extraction for when LLM is unavailable.
    Looks for common patterns in career page HTML.
    """
    from urllib.parse import urlparse, urljoin

    jobs = []
    seen_urls = set()

    # Pattern 1: Links with job-related text
    link_pattern = re.compile(
        r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
        re.IGNORECASE | re.DOTALL,
    )

    job_title_keywords = [
        "engineer", "developer", "designer", "analyst", "manager",
        "scientist", "architect", "lead", "intern", "associate",
        "consultant", "specialist", "coordinator", "executive",
    ]

    for match in link_pattern.finditer(html):
        href = match.group(1)
        text = re.sub(r"<[^>]+>", "", match.group(2)).strip()

        if not text or len(text) < 5 or len(text) > 150:
            continue

        # Check if the link text looks like a job title
        text_lower = text.lower()
        if any(kw in text_lower for kw in job_title_keywords):
            # Normalize URL
            url = href
            if not url.startswith("http"):
                url = urljoin(career_url, url)

            if url not in seen_urls:
                seen_urls.add(url)
                jobs.append({
                    "title": text,
                    "location": "Unknown",
                    "url": url,
                    "department": None,
                    "jd_text": "",
                    "source": "custom_regex",
                })

    logger.info(f"[job_extractor] Regex extracted {len(jobs)} jobs from {career_url}")
    return jobs


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    # Test with a sample HTML
    test_html = """
    <div class="job-listing">
        <a href="/careers/software-engineer">Software Engineer - Backend</a>
        <span>Bangalore, India</span>
    </div>
    <div class="job-listing">
        <a href="/careers/data-analyst">Data Analyst</a>
        <span>Remote</span>
    </div>
    """
    jobs = extract_jobs_with_regex(test_html, "https://example.com/careers")
    print(json.dumps(jobs, indent=2))
