from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from agents.state import JobLead
from services.resilience import CircuitBreaker

_EMAIL_REGEX = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
_job_page_breaker = CircuitBreaker("job_page_fetch")


@dataclass
class RecruiterResult:
    recruiter_name: str | None
    recruiter_email: str | None
    errors: list[str]


def _extract_email_from_text(text: str) -> str | None:
    match = _EMAIL_REGEX.search(text)
    return match.group(0) if match else None


def _infer_domain(job: JobLead) -> str | None:
    raw = job.get("url", "")
    if not raw:
        return None
    host = urlparse(raw).netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    return host or None


@retry(wait=wait_exponential(min=2, max=15), stop=stop_after_attempt(3), reraise=True)
def _fetch_page(url: str) -> str:
    response = requests.get(url, timeout=20, headers={"User-Agent": "job-agent/1.0"})
    response.raise_for_status()
    return response.text


def _guess_email_patterns(name: str, domain: str) -> list[str]:
    parts = [p for p in re.split(r"\s+", name.strip().lower()) if p]
    if not parts:
        return []
    first = parts[0]
    last = parts[-1] if len(parts) > 1 else ""
    guesses = [f"{first}@{domain}"]
    if last:
        guesses.extend(
            [
                f"{first}.{last}@{domain}",
                f"{first}{last}@{domain}",
                f"{first[0]}{last}@{domain}",
            ]
        )
    return guesses


def discover_recruiter(job: JobLead, current_match_score: float | None) -> RecruiterResult:
    errors: list[str] = []
    recruiter_name = job.get("recruiter_name") or "Hiring Team"
    recruiter_email = job.get("recruiter_email")
    if recruiter_email:
        return RecruiterResult(recruiter_name=recruiter_name, recruiter_email=recruiter_email, errors=[])

    jd_text = job.get("jd_text", "")
    email_from_text = _extract_email_from_text(jd_text)
    if email_from_text:
        return RecruiterResult(recruiter_name=recruiter_name, recruiter_email=email_from_text, errors=[])

    job_url = job.get("url", "")
    if job_url:
        if _job_page_breaker.allow():
            try:
                html = _fetch_page(job_url)
            except requests.RequestException as exc:
                _job_page_breaker.record_failure()
                errors.append(f"job page fetch failed: {exc}")
            else:
                page_email = _extract_email_from_text(html)
                if page_email:
                    _job_page_breaker.record_success()
                    return RecruiterResult(
                        recruiter_name=recruiter_name,
                        recruiter_email=page_email,
                        errors=errors,
                    )
                _job_page_breaker.record_success()
        else:
            errors.append("job page fetch circuit open.")

    domain = _infer_domain(job)
    if recruiter_name and domain:
        guesses = _guess_email_patterns(recruiter_name, domain)
        if guesses:
            return RecruiterResult(
                recruiter_name=recruiter_name,
                recruiter_email=guesses[0],
                errors=errors,
            )

    return RecruiterResult(recruiter_name=recruiter_name, recruiter_email=None, errors=errors)
