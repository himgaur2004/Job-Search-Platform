"""
apply_bot.py — Autonomous job application bot.

Supports:
  - LinkedIn Easy Apply (via li_at cookie + Playwright)
  - Greenhouse (standardized forms)
  - Lever (standardized forms)
  - Workday (heuristic multi-step)
  - Ashby HQ
  - SmartRecruiters
  - iCIMS
  - BambooHR
  - Workable
  - Jobvite
  - Breezy HR
  - Taleo (Oracle legacy)
  - Generic ATS (best-effort form fill)
"""
from __future__ import annotations

import os
import re
import time
import random
from pathlib import Path
from typing import Dict, Any, Optional
from urllib.parse import urlparse

_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


def _get_candidate() -> Dict[str, str]:
    """Load applicant details from environment — reloads .env on every call."""
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env", override=True)
    return {
        "first_name": os.getenv("APPLICANT_FIRST_NAME", ""),
        "last_name": os.getenv("APPLICANT_LAST_NAME", ""),
        "email": os.getenv("APPLICANT_EMAIL", ""),
        "phone": os.getenv("APPLICANT_PHONE", ""),
        "linkedin_url": os.getenv("APPLICANT_LINKEDIN_URL", ""),
        "years_exp": os.getenv("APPLICANT_YEARS_EXP", "0"),
        "full_name": f"{os.getenv('APPLICANT_FIRST_NAME', '')} {os.getenv('APPLICANT_LAST_NAME', '')}".strip(),
    }


def _get_resume_path() -> Optional[str]:
    """Returns resume PDF path from env, reloading .env first."""
    # If a tailored resume was generated for this job, use it instead of the default
    if "DYNAMIC_RESUME_PATH" in os.environ and Path(os.environ["DYNAMIC_RESUME_PATH"]).exists():
        return os.environ["DYNAMIC_RESUME_PATH"]

    from dotenv import load_dotenv
    load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env", override=True)
    path = os.getenv("RESUME_PDF_PATH", "")
    if path and Path(path).exists():
        return path
    return None


def _detect_ats(url: str) -> str:
    """Detect ATS type from job URL — supports 15+ platforms."""
    domain = urlparse(url).netloc.lower()
    path = urlparse(url).path.lower()

    if "linkedin.com" in domain:
        return "linkedin"
    if "greenhouse.io" in domain or "boards.greenhouse.io" in domain:
        return "greenhouse"
    if "lever.co" in domain or "jobs.lever.co" in domain:
        return "lever"
    if "myworkdayjobs.com" in domain or "workday.com" in domain:
        return "workday"
    if "jobs.ashbyhq.com" in domain or "ashbyhq.com" in domain:
        return "ashby"
    if "smartrecruiters.com" in domain:
        return "smartrecruiters"
    if "icims.com" in domain:
        return "icims"
    if "bamboohr.com" in domain:
        return "bamboohr"
    if "workable.com" in domain or "apply.workable.com" in domain:
        return "workable"
    if "jobvite.com" in domain or "jobs.jobvite.com" in domain:
        return "jobvite"
    if "breezy.hr" in domain or "app.breezy.hr" in domain:
        return "breezy"
    if "taleo.net" in domain or "tbe.taleo.net" in domain:
        return "taleo"
    if "successfactors.com" in domain or "sap.com" in domain:
        return "successfactors"
    if "recruitee.com" in domain or "careers.recruitee.com" in domain:
        return "recruitee"
    if "rippling.com" in domain or "jobs.rippling.com" in domain:
        return "rippling"
    return "generic"


def _resolve_apply_url(page, listing_url: str) -> str:
    """
    Given a job LISTING page, try to find and return the actual apply form URL.
    Returns the original URL if no apply link can be found.
    """
    apply_selectors = [
        "a[href*='apply']",
        "a:has-text('Apply Now')",
        "a:has-text('Apply for this job')",
        "a:has-text('Apply for this position')",
        "a#apply-button",
        "a.apply-btn",
        "button:has-text('Apply Now')",
        "button:has-text('Apply for Job')",
    ]
    for sel in apply_selectors:
        try:
            el = page.query_selector(sel)
            if el:
                href = el.get_attribute("href") or ""
                if href and href.startswith("http") and href != listing_url:
                    return href
        except Exception:
            pass
    return listing_url


def _fill_common_fields(page, candidate: Dict[str, str], resume_path: Optional[str]) -> None:
    """Fill common text fields and upload resume on any ATS page."""
    # Upload resume if file input is present
    if resume_path:
        try:
            file_inputs = page.query_selector_all("input[type='file']")
            for fi in file_inputs:
                try:
                    fi.set_input_files(resume_path)
                    time.sleep(2)
                    break
                except Exception:
                    pass
        except Exception:
            pass

    # Fill all text/email/tel inputs based on label context
    field_map = {
        "first": candidate["first_name"],
        "given": candidate["first_name"],
        "last": candidate["last_name"],
        "family": candidate["last_name"],
        "surname": candidate["last_name"],
        "full name": candidate["full_name"],
        "your name": candidate["full_name"],
        "name": candidate["full_name"],
        "email": candidate["email"],
        "phone": candidate["phone"],
        "mobile": candidate["phone"],
        "linkedin": candidate["linkedin_url"],
        "years": candidate["years_exp"],
        "experience": candidate["years_exp"],
    }

    inputs = page.query_selector_all(
        "input[type='text'], input[type='email'], input[type='tel'], "
        "input[type='number'], input:not([type])"
    )
    for inp in inputs:
        try:
            label_text = (
                inp.get_attribute("aria-label") or
                inp.get_attribute("placeholder") or
                inp.get_attribute("name") or
                inp.get_attribute("id") or ""
            ).lower()

            for key, value in field_map.items():
                if key in label_text and value:
                    current = inp.input_value()
                    if not current:
                        inp.fill(value)
                    break
        except Exception:
            pass


def _handle_radio_and_select(page, candidate: Dict[str, str]) -> None:
    """Auto-answer common yes/no radio buttons and dropdowns."""
    # "Are you authorized to work?" — answer Yes
    yes_patterns = [
        "label:has-text('Yes')",
        "input[value='Yes']",
        "input[value='yes']",
        "input[value='true']",
        "input[value='1']",
    ]
    # Try to find radios near authorization / sponsorship questions
    try:
        radios = page.query_selector_all("input[type='radio']")
        for r in radios:
            parent_text = ""
            try:
                parent_text = page.evaluate("el => el.closest('fieldset, div, section')?.innerText || ''", r).lower()
            except Exception:
                pass
            if any(kw in parent_text for kw in ["authorized", "eligible to work", "legally", "sponsorship", "require visa"]):
                val = r.get_attribute("value") or ""
                if val.lower() in ("yes", "true", "1", "no_sponsor", "authorized"):
                    r.click()
                    break
    except Exception:
        pass

    # Handle select dropdowns — "Country", "State" etc.
    try:
        selects = page.query_selector_all("select")
        for sel in selects:
            name = (sel.get_attribute("name") or sel.get_attribute("id") or "").lower()
            if "country" in name:
                try:
                    sel.select_option(label="India")
                except Exception:
                    pass
    except Exception:
        pass



def _extract_linkedin_external_url(job_url: str, page=None) -> Optional[str]:
    """
    Extract the external company apply URL from a LinkedIn job listing.

    Strategy cascade:
      1. Check if LinkedIn is showing a sign-up gate (expired li_at) — parse company/title
         and use the LinkedIn guest API to get job details without auth.
      2. Use Google Jobs public search to find the external apply URL by job title + company.
      3. JSON-LD schema.org in guest API HTML.
      4. Playwright: click Apply, capture popup/new-tab URL.
      5. Playwright: scan the fully-rendered page HTML for apply URL patterns.
    Returns None if all strategies fail.
    """
    import re
    import json as _json
    import requests
    from bs4 import BeautifulSoup
    from urllib.parse import quote_plus

    def _is_external(url: str) -> bool:
        if not url or not url.startswith("http"):
            return False
        blocked = ["linkedin.com", "login", "signup", "authwall", "checkpoint"]
        return not any(b in url.lower() for b in blocked)

    # Extract job ID from URL
    job_id_match = re.search(r"[-/](\d{9,})\b", job_url)
    job_id = job_id_match.group(1) if job_id_match else None

    # ── Strategy 1: LinkedIn guest API ──────────────────────────────────────
    # The guest API works without auth and returns structured HTML.
    # It won't have the apply URL directly, but gives us company name + title.
    company_name = ""
    job_title = ""
    if job_id:
        try:
            api_url = f"https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{job_id}"
            resp = requests.get(
                api_url,
                headers={"User-Agent": _USER_AGENT, "Accept-Language": "en-US,en;q=0.9"},
                timeout=12,
            )
            if resp.ok:
                soup = BeautifulSoup(resp.text, "lxml")

                # Extract company name and job title for Strategy 2
                title_tag = soup.select_one(".top-card-layout__title, h2.top-card-layout__title")
                company_tag = soup.select_one(".top-card-layout__company-name, a.topcard__org-name-link")
                if title_tag:
                    job_title = title_tag.get_text(strip=True)
                if company_tag:
                    company_name = company_tag.get_text(strip=True)

                # Scan the HTML for embedded apply URL patterns
                html = resp.text
                for pattern in [
                    r'"companyApplyUrl"\s*:\s*"([^"]+)"',
                    r'"externalApplyUrl"\s*:\s*"([^"]+)"',
                    r'"applyUrl"\s*:\s*"([^"]+)"',
                ]:
                    m = re.search(pattern, html)
                    if m:
                        url = m.group(1).replace("\\u0026", "&").replace("\\/", "/")
                        if _is_external(url):
                            print(f"[apply_bot] Strategy 1 (guest API JSON) found: {url}")
                            return url

                # JSON-LD schema.org
                for script in soup.find_all("script", type="application/ld+json"):
                    try:
                        data = _json.loads(script.string or "")
                        objs = data if isinstance(data, list) else [data]
                        for obj in objs:
                            for key in ("url", "sameAs", "applicationContact"):
                                val = obj.get(key)
                                if isinstance(val, dict):
                                    val = val.get("url", "")
                                if isinstance(val, str) and _is_external(val):
                                    print(f"[apply_bot] Strategy 1b (JSON-LD) found: {val}")
                                    return val
                    except Exception:
                        pass
        except Exception as e:
            print(f"[apply_bot] Strategy 1 failed: {e}")

    # ── Strategy 2: Parse company/title from URL slug + Google Jobs scrape ──
    # Extract from URL slug if API didn't give us the info
    if not company_name or not job_title:
        # URL format: /jobs/view/job-title-at-company-name-JOBID
        slug_match = re.search(r"/jobs/view/(.+?)-\d{9,}", job_url)
        if slug_match:
            slug = slug_match.group(1).replace("-", " ")
            at_idx = slug.rfind(" at ")
            if at_idx > 0:
                job_title = job_title or slug[:at_idx].strip()
                company_name = company_name or slug[at_idx + 4:].strip()

    if job_title and company_name:
        try:
            # Use Google's "site:boards.greenhouse.io OR site:jobs.lever.co OR site:myworkdayjobs.com"
            # to find the direct ATS link for this job
            query = f'"{job_title}" "{company_name}" apply site:boards.greenhouse.io OR site:jobs.lever.co OR site:myworkdayjobs.com OR site:jobs.ashbyhq.com OR site:apply.workable.com'
            search_url = f"https://www.google.com/search?q={quote_plus(query)}&num=5"
            resp = requests.get(
                search_url,
                headers={"User-Agent": _USER_AGENT, "Accept-Language": "en-US,en;q=0.9"},
                timeout=10,
            )
            if resp.ok:
                soup = BeautifulSoup(resp.text, "lxml")
                for a in soup.find_all("a", href=True):
                    href = a["href"]
                    # Google wraps links in /url?q=...
                    if href.startswith("/url?q="):
                        href = href[7:].split("&")[0]
                    if _is_external(href) and any(
                        ats in href for ats in [
                            "greenhouse.io", "lever.co", "myworkdayjobs.com",
                            "ashbyhq.com", "workable.com", "bamboohr.com",
                            "icims.com", "smartrecruiters.com",
                        ]
                    ):
                        from urllib.parse import unquote
                        href = unquote(href)
                        print(f"[apply_bot] Strategy 2 (Google Jobs ATS search) found: {href}")
                        return href
        except Exception as e:
            print(f"[apply_bot] Strategy 2 failed: {e}")

        # Fallback: try direct Greenhouse/Lever API lookup by company slug
        company_slug = re.sub(r"[^a-z0-9]", "", company_name.lower())
        for ats_url in [
            f"https://boards-api.greenhouse.io/v1/boards/{company_slug}/jobs",
            f"https://api.lever.co/v0/postings/{company_slug}",
        ]:
            try:
                resp = requests.get(ats_url, timeout=8)
                if resp.ok:
                    data = resp.json()
                    jobs_list = data.get("jobs", data) if isinstance(data, dict) else data
                    for j in (jobs_list if isinstance(jobs_list, list) else []):
                        t = (j.get("title") or j.get("text") or "").lower()
                        if job_title.lower()[:20] in t:
                            link = j.get("absolute_url") or j.get("hostedUrl") or ""
                            if _is_external(link):
                                print(f"[apply_bot] Strategy 2b (ATS API lookup) found: {link}")
                                return link
            except Exception:
                pass

    # ── Strategies 3 & 4: Playwright-based ──────────────────────────────────
    if page is None:
        return None

    # Check if LinkedIn is showing a sign-up gate (expired session)
    try:
        modal = page.query_selector(".sign-up-modal, .authwall-join-form, [data-tracking-control-name*='authwall']")
        if modal:
            print("[apply_bot] LinkedIn sign-up gate detected (li_at may be expired). Skipping Playwright strategies.")
            return None
    except Exception:
        pass

    # Strategy 3: Click Apply and capture popup/new-tab
    try:
        page.wait_for_timeout(2000)
        apply_btn = page.query_selector(
            "button.jobs-apply-button:not(.sign-up-modal__outlet), "
            "a.jobs-apply-button:not(.sign-up-modal__outlet), "
            ".jobs-apply-button--top-card"
        )
        if apply_btn:
            href = apply_btn.get_attribute("href") or ""
            if _is_external(href):
                print(f"[apply_bot] Strategy 3a (href attr) found: {href}")
                return href

            try:
                with page.context.expect_event("page", timeout=10000) as popup_info:
                    apply_btn.click()
                popup = popup_info.value
                popup.wait_for_load_state("domcontentloaded", timeout=15000)
                popup_url = popup.url
                popup.close()
                if _is_external(popup_url):
                    print(f"[apply_bot] Strategy 3b (popup) found: {popup_url}")
                    return popup_url
            except Exception:
                pass
    except Exception as e:
        print(f"[apply_bot] Strategy 3 failed: {e}")

    # Strategy 4: Scan rendered page HTML for apply URL patterns
    try:
        html = page.content()
        for pattern in [
            r'"companyApplyUrl"\s*:\s*"([^"]+)"',
            r'"externalApplyUrl"\s*:\s*"([^"]+)"',
            r'"applyUrl"\s*:\s*"([^"]+)"',
        ]:
            m = re.search(pattern, html)
            if m:
                url = m.group(1).replace("\\u0026", "&").replace("\\/", "/")
                if _is_external(url):
                    print(f"[apply_bot] Strategy 4 (page HTML scan) found: {url}")
                    return url
    except Exception:
        pass

    # Strategy 5 (last resort): Try the company's careers page directly
    if company_name:
        company_slug_web = re.sub(r"[^a-z0-9]", "", company_name.lower())
        careers_urls = [
            f"https://www.{company_slug_web}.com/careers",
            f"https://careers.{company_slug_web}.com",
            f"https://jobs.{company_slug_web}.com",
            f"https://www.{company_slug_web}.com/jobs",
        ]
        for careers_url in careers_urls:
            try:
                resp = requests.get(
                    careers_url,
                    headers={"User-Agent": _USER_AGENT},
                    timeout=8,
                    allow_redirects=True,
                )
                if resp.ok and resp.url and _is_external(resp.url):
                    # Check if any known ATS appears in the final redirect URL
                    final_url = resp.url
                    if any(ats in final_url for ats in [
                        "greenhouse.io", "lever.co", "myworkdayjobs.com",
                        "ashbyhq.com", "workable.com", "bamboohr.com",
                        "icims.com", "smartrecruiters.com",
                    ]):
                        print(f"[apply_bot] Strategy 5 (careers redirect) found: {final_url}")
                        return final_url
                    print(f"[apply_bot] Strategy 5 (careers page) exists but no known ATS: {final_url}")
                    return final_url
            except Exception:
                pass

    return None


def apply_linkedin(job_url: str) -> Dict[str, Any]:
    """
    Apply via LinkedIn. Strategy:
    1. Try Easy Apply (li_at cookie + Playwright form fill).
    2. If no Easy Apply button, extract the external apply URL and route to the
       correct ATS handler (Greenhouse, Workday, Lever, generic, etc.).
    """
    from playwright.sync_api import sync_playwright

    li_at = os.getenv("LINKEDIN_LI_AT", "")
    candidate = _get_candidate()
    resume_path = _get_resume_path()

    if not candidate["email"]:
        return {"success": False, "error": "APPLICANT_EMAIL not set"}

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
        )
        ctx = browser.new_context(
            user_agent=_USER_AGENT,
            viewport={"width": 1440, "height": 900},
        )
        page = ctx.new_page()
        page.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )

        try:
            # Set li_at BEFORE first navigation so LinkedIn sees it immediately
            if li_at:
                ctx.add_cookies([{"name": "li_at", "value": li_at, "domain": ".linkedin.com", "path": "/"}])

            # Normalize job_url to avoid TOO_MANY_REDIRECTS on regional domains (e.g. in.linkedin.com)
            import re
            job_id_match = re.search(r"[-/](\d{9,})\b", job_url)
            if job_id_match:
                job_url_auth = f"https://www.linkedin.com/jobs/view/{job_id_match.group(1)}/"
            else:
                job_url_auth = job_url

            page.goto(job_url_auth, wait_until="domcontentloaded", timeout=60000)
            time.sleep(random.uniform(3, 5))

            # ── Path 1: LinkedIn Easy Apply ──────────────────────────────────
            easy_apply = page.query_selector(
                "button.jobs-apply-button[aria-label*='Easy Apply'], "
                "button:has-text('Easy Apply')"
            )
            if easy_apply:
                easy_apply.click()
                time.sleep(2)

                for step in range(8):
                    _fill_common_fields(page, candidate, resume_path if step == 0 else None)
                    _handle_radio_and_select(page, candidate)

                    if step == 0 and resume_path:
                        upload_btn = page.query_selector("label:has-text('Upload'), button:has-text('Upload resume')")
                        if upload_btn:
                            upload_btn.click()
                            time.sleep(1)

                    submit_btn = page.query_selector(
                        "button[aria-label='Submit application'], "
                        "button:has-text('Submit application')"
                    )
                    if submit_btn:
                        submit_btn.click()
                        time.sleep(2)
                        return {"success": True, "error": None, "ats": "linkedin_easy_apply"}

                    next_btn = page.query_selector(
                        "button[aria-label='Continue to next step'], "
                        "button:has-text('Next'), "
                        "button:has-text('Review')"
                    )
                    if next_btn:
                        next_btn.click()
                        time.sleep(1.5)
                    else:
                        break

                return {"success": False, "error": "Easy Apply form did not reach submission step"}

            # ── Path 2: External Apply — multi-strategy URL extraction ────────
            print(f"[apply_bot] No Easy Apply on LinkedIn. Looking for external apply link...")

            external_url = _extract_linkedin_external_url(job_url, page)

            if not external_url:
                # Check if it was blocked by a sign-up gate
                is_gated = False
                try:
                    is_gated = bool(page.query_selector(".sign-up-modal, .authwall-join-form"))
                except Exception:
                    pass
                err = (
                    "LinkedIn session expired (li_at cookie is stale). "
                    "Go to linkedin.com in Chrome, open DevTools → Application → Cookies → li_at, copy the value and update LINKEDIN_LI_AT in .env"
                    if is_gated else
                    "LinkedIn job has no Easy Apply and external apply URL could not be extracted automatically"
                )
                return {"success": False, "error": err, "ats": "linkedin_external_unknown"}

            print(f"[apply_bot] LinkedIn → external URL: {external_url}")
            external_ats = _detect_ats(external_url)
            print(f"[apply_bot] External ATS detected: {external_ats}")

            # Close LinkedIn browser and hand off to the right ATS handler
            browser.close()

            if external_ats == "greenhouse":
                return apply_greenhouse(external_url)
            elif external_ats == "lever":
                return apply_lever(external_url)
            elif external_ats == "workday":
                return apply_workday(external_url)
            elif external_ats == "icims":
                return apply_icims(external_url)
            elif external_ats == "bamboohr":
                return apply_bamboohr(external_url)
            elif external_ats == "workable":
                return apply_workable(external_url)
            elif external_ats == "smartrecruiters":
                return apply_smartrecruiters(external_url)
            elif external_ats == "jobvite":
                return apply_jobvite(external_url)
            else:
                return apply_generic(external_url)

        except Exception as exc:
            return {"success": False, "error": str(exc)}
        finally:
            try:
                browser.close()
            except Exception:
                pass  # already closed in the external fallback path



def apply_greenhouse(job_url: str) -> Dict[str, Any]:
    """Apply to a Greenhouse-hosted job."""
    from playwright.sync_api import sync_playwright

    candidate = _get_candidate()
    resume_path = _get_resume_path()

    if not candidate["email"]:
        return {"success": False, "error": "APPLICANT_EMAIL not set"}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page(user_agent=_USER_AGENT)

        try:
            page.goto(job_url, wait_until="domcontentloaded", timeout=60000)
            time.sleep(random.uniform(2, 3))

            apply_btn = page.query_selector("a#btn-apply, a:has-text('Apply for this job'), button:has-text('Apply')")
            if apply_btn:
                apply_btn.click()
                page.wait_for_load_state("domcontentloaded")
                time.sleep(2)

            _fill_common_fields(page, candidate, resume_path)
            _handle_radio_and_select(page, candidate)

            for field_id, value in [
                ("first_name", candidate["first_name"]),
                ("last_name", candidate["last_name"]),
                ("email", candidate["email"]),
                ("phone", candidate["phone"]),
            ]:
                el = page.query_selector(f"#question_{field_id}, input[name='{field_id}'], #{field_id}")
                if el and value:
                    try:
                        if not el.input_value():
                            el.fill(value)
                    except Exception:
                        pass

            submit = page.query_selector("input[type='submit'], button[type='submit'], button:has-text('Submit Application')")
            if submit:
                submit.click()
                time.sleep(3)
                return {"success": True, "error": None, "ats": "greenhouse"}

            return {"success": False, "error": "Submit button not found"}
        except Exception as exc:
            return {"success": False, "error": str(exc)}
        finally:
            browser.close()


def apply_lever(job_url: str) -> Dict[str, Any]:
    """Apply to a Lever-hosted job."""
    from playwright.sync_api import sync_playwright

    candidate = _get_candidate()
    resume_path = _get_resume_path()

    if not candidate["email"]:
        return {"success": False, "error": "APPLICANT_EMAIL not set"}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page(user_agent=_USER_AGENT)

        try:
            page.goto(job_url, wait_until="domcontentloaded", timeout=60000)
            time.sleep(random.uniform(2, 3))

            apply_btn = page.query_selector("a.postings-btn, a:has-text('Apply'), button:has-text('Apply')")
            if apply_btn:
                apply_btn.click()
                page.wait_for_load_state("domcontentloaded")
                time.sleep(2)

            _fill_common_fields(page, candidate, resume_path)
            _handle_radio_and_select(page, candidate)

            for selector, value in [
                ("input[name='name']", candidate["full_name"]),
                ("input[name='email']", candidate["email"]),
                ("input[name='phone']", candidate["phone"]),
                ("input[name='urls[LinkedIn]']", candidate["linkedin_url"]),
            ]:
                el = page.query_selector(selector)
                if el and value:
                    try:
                        if not el.input_value():
                            el.fill(value)
                    except Exception:
                        pass

            submit = page.query_selector("button[type='submit'], input[type='submit']")
            if submit:
                submit.click()
                time.sleep(3)
                return {"success": True, "error": None, "ats": "lever"}

            return {"success": False, "error": "Submit button not found"}
        except Exception as exc:
            return {"success": False, "error": str(exc)}
        finally:
            browser.close()


def apply_workday(job_url: str) -> Dict[str, Any]:
    """Apply to a Workday-hosted job (multi-step, heuristic)."""
    from playwright.sync_api import sync_playwright

    candidate = _get_candidate()
    resume_path = _get_resume_path()

    if not candidate["email"]:
        return {"success": False, "error": "APPLICANT_EMAIL not set"}

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
        )
        page = browser.new_page(user_agent=_USER_AGENT)

        try:
            page.goto(job_url, wait_until="domcontentloaded", timeout=60000)
            time.sleep(random.uniform(3, 5))

            # Try clicking Apply
            apply_btn = page.query_selector(
                "a[data-automation-id='applyNowButton'], "
                "button[data-automation-id='applyNowButton'], "
                "button:has-text('Apply'), a:has-text('Apply Now')"
            )
            if apply_btn:
                apply_btn.click()
                time.sleep(3)

            # Workday may open in new tab — get active page
            pages = page.context.pages
            if len(pages) > 1:
                page = pages[-1]
                time.sleep(2)

            # Multi-step Workday form — up to 10 steps
            for step in range(10):
                _fill_common_fields(page, candidate, resume_path if step == 0 else None)
                _handle_radio_and_select(page, candidate)

                # Workday-specific: autofill email
                wd_email = page.query_selector("[data-automation-id='email']")
                if wd_email:
                    try:
                        if not wd_email.input_value():
                            wd_email.fill(candidate["email"])
                    except Exception:
                        pass

                # Check for Submit
                submit = page.query_selector(
                    "button[data-automation-id='bottom-navigation-btn-create-account'], "
                    "button:has-text('Submit'), "
                    "button[aria-label='Submit']"
                )
                if submit:
                    submit.click()
                    time.sleep(3)
                    return {"success": True, "error": None, "ats": "workday"}

                # Next / Save & Continue
                next_btn = page.query_selector(
                    "button[data-automation-id='pageHeaderButton'], "
                    "button:has-text('Next'), "
                    "button:has-text('Save and Continue'), "
                    "button:has-text('Continue')"
                )
                if next_btn:
                    next_btn.click()
                    time.sleep(2)
                else:
                    break

            return {"success": False, "error": "Workday form did not reach submission"}
        except Exception as exc:
            return {"success": False, "error": str(exc)}
        finally:
            browser.close()


def apply_icims(job_url: str) -> Dict[str, Any]:
    """Apply to an iCIMS-hosted job."""
    from playwright.sync_api import sync_playwright

    candidate = _get_candidate()
    resume_path = _get_resume_path()

    if not candidate["email"]:
        return {"success": False, "error": "APPLICANT_EMAIL not set"}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page(user_agent=_USER_AGENT)

        try:
            page.goto(job_url, wait_until="domcontentloaded", timeout=60000)
            time.sleep(random.uniform(2, 4))

            # iCIMS has "Apply Now" → opens modal or new page
            apply_btn = page.query_selector(
                "a.iCIMS_Anchor, a:has-text('Apply Now'), button:has-text('Apply Now')"
            )
            if apply_btn:
                apply_btn.click()
                page.wait_for_load_state("domcontentloaded", timeout=15000)
                time.sleep(2)

            _fill_common_fields(page, candidate, resume_path)
            _handle_radio_and_select(page, candidate)

            submit = page.query_selector(
                "input[type='submit'], button[type='submit'], "
                "button:has-text('Submit'), a:has-text('Submit Application')"
            )
            if submit:
                submit.click()
                time.sleep(3)
                return {"success": True, "error": None, "ats": "icims"}

            return {"success": False, "error": "iCIMS: Submit button not found"}
        except Exception as exc:
            return {"success": False, "error": str(exc)}
        finally:
            browser.close()


def apply_bamboohr(job_url: str) -> Dict[str, Any]:
    """Apply to a BambooHR-hosted job."""
    from playwright.sync_api import sync_playwright

    candidate = _get_candidate()
    resume_path = _get_resume_path()

    if not candidate["email"]:
        return {"success": False, "error": "APPLICANT_EMAIL not set"}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page(user_agent=_USER_AGENT)

        try:
            page.goto(job_url, wait_until="domcontentloaded", timeout=60000)
            time.sleep(random.uniform(2, 3))

            apply_btn = page.query_selector(
                "a.btn-primary:has-text('Apply'), button:has-text('Apply'), "
                "a:has-text('Apply Now')"
            )
            if apply_btn:
                apply_btn.click()
                page.wait_for_load_state("domcontentloaded", timeout=15000)
                time.sleep(2)

            _fill_common_fields(page, candidate, resume_path)
            _handle_radio_and_select(page, candidate)

            # BambooHR specific fields
            for selector, value in [
                ("input#firstName", candidate["first_name"]),
                ("input#lastName", candidate["last_name"]),
                ("input#email", candidate["email"]),
                ("input#phone", candidate["phone"]),
            ]:
                el = page.query_selector(selector)
                if el and value:
                    try:
                        if not el.input_value():
                            el.fill(value)
                    except Exception:
                        pass

            submit = page.query_selector(
                "button[type='submit']:has-text('Apply'), button:has-text('Submit')"
            )
            if submit:
                submit.click()
                time.sleep(3)
                return {"success": True, "error": None, "ats": "bamboohr"}

            return {"success": False, "error": "BambooHR: Submit button not found"}
        except Exception as exc:
            return {"success": False, "error": str(exc)}
        finally:
            browser.close()


def apply_workable(job_url: str) -> Dict[str, Any]:
    """Apply to a Workable-hosted job."""
    from playwright.sync_api import sync_playwright

    candidate = _get_candidate()
    resume_path = _get_resume_path()

    if not candidate["email"]:
        return {"success": False, "error": "APPLICANT_EMAIL not set"}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page(user_agent=_USER_AGENT)

        try:
            page.goto(job_url, wait_until="domcontentloaded", timeout=60000)
            time.sleep(random.uniform(2, 3))

            apply_btn = page.query_selector("button:has-text('Apply'), a:has-text('Apply')")
            if apply_btn:
                apply_btn.click()
                page.wait_for_load_state("domcontentloaded", timeout=15000)
                time.sleep(2)

            _fill_common_fields(page, candidate, resume_path)
            _handle_radio_and_select(page, candidate)

            # Workable specific
            for selector, value in [
                ("input[name='firstname']", candidate["first_name"]),
                ("input[name='lastname']", candidate["last_name"]),
                ("input[name='email']", candidate["email"]),
                ("input[name='phone']", candidate["phone"]),
            ]:
                el = page.query_selector(selector)
                if el and value:
                    try:
                        if not el.input_value():
                            el.fill(value)
                    except Exception:
                        pass

            submit = page.query_selector("button[type='submit']")
            if submit:
                submit.click()
                time.sleep(3)
                return {"success": True, "error": None, "ats": "workable"}

            return {"success": False, "error": "Workable: Submit button not found"}
        except Exception as exc:
            return {"success": False, "error": str(exc)}
        finally:
            browser.close()


def apply_smartrecruiters(job_url: str) -> Dict[str, Any]:
    """Apply to a SmartRecruiters-hosted job."""
    from playwright.sync_api import sync_playwright

    candidate = _get_candidate()
    resume_path = _get_resume_path()

    if not candidate["email"]:
        return {"success": False, "error": "APPLICANT_EMAIL not set"}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page(user_agent=_USER_AGENT)

        try:
            page.goto(job_url, wait_until="domcontentloaded", timeout=60000)
            time.sleep(random.uniform(2, 3))

            apply_btn = page.query_selector(
                "button.sma-button, button:has-text('Apply'), a:has-text('Apply Now')"
            )
            if apply_btn:
                apply_btn.click()
                page.wait_for_load_state("domcontentloaded", timeout=15000)
                time.sleep(2)

            _fill_common_fields(page, candidate, resume_path)
            _handle_radio_and_select(page, candidate)

            submit = page.query_selector("button[type='submit'], button:has-text('Submit')")
            if submit:
                submit.click()
                time.sleep(3)
                return {"success": True, "error": None, "ats": "smartrecruiters"}

            return {"success": False, "error": "SmartRecruiters: Submit button not found"}
        except Exception as exc:
            return {"success": False, "error": str(exc)}
        finally:
            browser.close()


def apply_jobvite(job_url: str) -> Dict[str, Any]:
    """Apply to a Jobvite-hosted job."""
    from playwright.sync_api import sync_playwright

    candidate = _get_candidate()
    resume_path = _get_resume_path()

    if not candidate["email"]:
        return {"success": False, "error": "APPLICANT_EMAIL not set"}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page(user_agent=_USER_AGENT)

        try:
            page.goto(job_url, wait_until="domcontentloaded", timeout=60000)
            time.sleep(random.uniform(2, 3))

            apply_btn = page.query_selector("a.jv-btn-apply, a:has-text('Apply'), button:has-text('Apply')")
            if apply_btn:
                apply_btn.click()
                page.wait_for_load_state("domcontentloaded", timeout=15000)
                time.sleep(2)

            _fill_common_fields(page, candidate, resume_path)
            _handle_radio_and_select(page, candidate)

            submit = page.query_selector(
                "button[type='submit'], input[type='submit'], "
                "button:has-text('Submit Application')"
            )
            if submit:
                submit.click()
                time.sleep(3)
                return {"success": True, "error": None, "ats": "jobvite"}

            return {"success": False, "error": "Jobvite: Submit button not found"}
        except Exception as exc:
            return {"success": False, "error": str(exc)}
        finally:
            browser.close()


def apply_generic(job_url: str) -> Dict[str, Any]:
    """
    Best-effort apply to any job page (Breezy, Taleo, SuccessFactors, Recruitee, Rippling, or unknown ATS).
    Tries to resolve the actual apply form URL from the listing page.
    """
    from playwright.sync_api import sync_playwright

    candidate = _get_candidate()
    resume_path = _get_resume_path()

    if not candidate["email"]:
        return {"success": False, "error": "APPLICANT_EMAIL not set"}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page(user_agent=_USER_AGENT)

        try:
            page.goto(job_url, wait_until="domcontentloaded", timeout=60000)
            time.sleep(random.uniform(2, 4))

            # Attempt to resolve the actual apply form URL
            resolved_url = _resolve_apply_url(page, job_url)
            if resolved_url != job_url:
                print(f"[apply_bot] Resolved apply URL: {resolved_url}")
                page.goto(resolved_url, wait_until="domcontentloaded", timeout=60000)
                time.sleep(2)

            # Click Apply button
            apply_btn = page.query_selector(
                "button:has-text('Apply'), a:has-text('Apply Now'), "
                "button:has-text('Apply Now'), a:has-text('Apply')"
            )
            if apply_btn:
                apply_btn.click()
                time.sleep(3)

            _fill_common_fields(page, candidate, resume_path)
            _handle_radio_and_select(page, candidate)

            # Multi-step handling — up to 5 steps
            for _ in range(5):
                submit = page.query_selector(
                    "button[type='submit'], input[type='submit'], "
                    "button:has-text('Submit'), button:has-text('Send Application'), "
                    "button:has-text('Complete Application')"
                )
                if submit:
                    submit.click()
                    time.sleep(3)
                    return {"success": True, "error": None, "ats": "generic"}

                next_btn = page.query_selector(
                    "button:has-text('Next'), button:has-text('Continue'), "
                    "button:has-text('Save and Next')"
                )
                if next_btn:
                    _fill_common_fields(page, candidate, None)
                    _handle_radio_and_select(page, candidate)
                    next_btn.click()
                    time.sleep(2)
                else:
                    break

            return {"success": False, "error": "Could not find submit button after form fill"}
        except Exception as exc:
            return {"success": False, "error": str(exc)}
        finally:
            browser.close()


def generate_tailored_resume(job_url: str, jd_text: str = "") -> Optional[str]:
    """
    Generate a JD-tailored PDF resume using the LLM resume agent.
    Returns path to generated PDF, or None if generation fails.
    """
    try:
        from agents.resume_agent import build_resume_graph
        import tempfile

        graph = build_resume_graph()
        state = {
            "current_job": {"url": job_url, "jd_text": jd_text},
            "pdf_path": None,
            "latex_content": None,
            "errors": [],
        }
        result = graph.invoke(state)
        return result.get("pdf_path")
    except Exception as exc:
        print(f"[apply_bot] Resume generation failed: {exc}")
        return None


def apply_to_job(
    job_url: str,
    resume_mode: str = "prebuilt",
    jd_text: str = "",
) -> Dict[str, Any]:
    """
    Main entry point: detect ATS and route to correct apply function.

    Args:
        job_url: The job listing or apply URL.
        resume_mode: "prebuilt" uses RESUME_PDF_PATH env var.
                     "generate" creates a JD-tailored resume via the LLM resume agent.
        jd_text: Job description text (used when resume_mode="generate").
    """
    ats = _detect_ats(job_url)
    print(f"[apply_bot] Applying to {job_url} via {ats} (resume_mode={resume_mode})")

    # Generate tailored resume if requested
    if resume_mode == "generate" and jd_text:
        generated_path = generate_tailored_resume(job_url, jd_text)
        if generated_path:
            # Temporarily set env so _get_resume_path() picks it up
            os.environ["DYNAMIC_RESUME_PATH"] = generated_path
            print(f"[apply_bot] Using generated resume: {generated_path}")

    # Random human-like delay before applying
    time.sleep(random.uniform(3, 8))

    if ats == "linkedin":
        return apply_linkedin(job_url)
    elif ats == "greenhouse":
        return apply_greenhouse(job_url)
    elif ats == "lever":
        return apply_lever(job_url)
    elif ats == "workday":
        return apply_workday(job_url)
    elif ats == "icims":
        return apply_icims(job_url)
    elif ats == "bamboohr":
        return apply_bamboohr(job_url)
    elif ats == "workable":
        return apply_workable(job_url)
    elif ats == "smartrecruiters":
        return apply_smartrecruiters(job_url)
    elif ats == "jobvite":
        return apply_jobvite(job_url)
    else:
        # ashby, breezy, taleo, successfactors, recruitee, rippling, generic
        return apply_generic(job_url)
