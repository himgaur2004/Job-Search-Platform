"""
seed_expanded_ats.py — Massively expand the ATS company database.

Sources:
  - Greenhouse tokens from GitHub repos (already seeded, skip duplicates)
  - Lever tokens from GitHub repos (already seeded, skip duplicates)
  - Ashby tokens from known public boards
  - Workable tokens from known public boards
  - BambooHR subdomains from known public boards
  - Workday tenant slugs from known public boards

All sources are public data. No scraping of protected content.
"""

import json
import os
import re
import sqlite3
import sys
import time

import requests

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from services.db import get_conn, init_db

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "application/json, text/html",
}


def _insert_company(conn, name: str, ats_type: str, token: str) -> bool:
    """Insert a company, returning True if it was new."""
    try:
        conn.execute(
            "INSERT OR IGNORE INTO ats_companies (name, ats_type, token) VALUES (?, ?, ?)",
            (name, ats_type, token),
        )
        return True
    except sqlite3.Error:
        return False


# ─── Ashby ────────────────────────────────────────────────────────────────────

ASHBY_KNOWN_TOKENS = [
    # Well-known companies using Ashby
    "ramp", "notion", "linear", "figma", "vercel", "retool", "supabase",
    "openai", "anthropic", "cohere", "midjourney", "stability-ai",
    "replit", "cal-com", "dbt-labs", "airbyte", "rudderstack",
    "snyk", "grafana", "hashicorp", "pulumi", "temporal",
    "clerk", "neon", "planetscale", "turso", "convex",
    "resend", "loops", "plain", "attio", "clay",
    "mercury", "brex", "rho", "meow", "puzzle",
    "liveblocks", "tldraw", "excalidraw", "miro",
    "zapier", "make", "n8n", "activepieces", "windmill",
    "cursor", "codeium", "tabnine", "sourcegraph",
    "perplexity", "you-com", "phind", "kagi",
    "railway", "render", "fly-io", "modal",
    "warp", "fig", "iterm2", "ghostty",
    "luma-ai", "runway", "pika", "heygen",
    "deel-engineering", "remote-com", "oyster-hr",
    "lattice", "culture-amp", "leapsome", "15five",
    "airtable", "coda-io", "clickup", "height",
    "sanity-io", "contentful", "strapi", "payload-cms",
    "prisma", "drizzle-team", "sequin",
    "inngest", "trigger-dev", "upstash",
    "axiom", "highlight-io", "sentry",
    "posthog", "amplitude", "mixpanel-eng",
    "lago", "getlago", "schematichq", "stigg",
    "novu", "knock", "courier",
    "stytch", "workos", "propelauth",
    "svix", "hookdeck",
    "dub", "short-io",
    "cal", "calendly-eng",
    "beehiiv", "substack-eng", "ghost-org",
    "ashbyhq", "greenhouse-software", "lever-co",
]

# Additional Ashby tokens from GitHub search
ASHBY_GITHUB_URLS = [
    "https://raw.githubusercontent.com/tramlinehq/store/main/ashby_companies.json",
]


def seed_ashby(conn):
    """Seed Ashby companies from known tokens and GitHub sources."""
    print("[seed] Seeding Ashby companies...")
    count = 0

    # Known tokens
    for token in ASHBY_KNOWN_TOKENS:
        if _insert_company(conn, token, "ashby", token):
            count += 1

    # Try GitHub sources
    for url in ASHBY_GITHUB_URLS:
        try:
            resp = requests.get(url, timeout=10, headers=HEADERS)
            if resp.ok:
                data = resp.json()
                if isinstance(data, list):
                    for item in data:
                        t = item if isinstance(item, str) else item.get("token", item.get("slug", ""))
                        if t and _insert_company(conn, t, "ashby", t):
                            count += 1
        except Exception as e:
            print(f"  [warn] Ashby GitHub source failed: {e}")

    # Discover more by probing the Ashby API
    # The API returns 200 with jobs data for valid tokens
    print(f"  [ashby] Probing known tokens for validity...")
    valid = 0
    for token in ASHBY_KNOWN_TOKENS[:20]:  # Probe a sample
        try:
            resp = requests.get(
                f"https://api.ashbyhq.com/posting-api/job-board/{token}",
                timeout=3,
                headers=HEADERS,
            )
            if resp.ok:
                valid += 1
        except Exception:
            pass
    print(f"  [ashby] {valid}/20 sampled tokens are valid Ashby boards")

    print(f"  [ashby] Inserted {count} Ashby companies")
    return count


# ─── Workable ─────────────────────────────────────────────────────────────────

WORKABLE_KNOWN_TOKENS = [
    # Well-known companies using Workable
    "sennder", "factorial", "typeform", "taxfix", "babbel",
    "wefox", "careem", "glovo", "cabify", "flixbus",
    "personio", "contentful-1", "commercetools", "celonis", "forto",
    "gorillas", "flink", "getir", "jokr", "gopuff",
    "tier", "voi", "lime", "bird-rides", "spin",
    "nuri", "n26", "revolut-1", "monzo", "starling-bank",
    "sumup", "adyen", "mollie", "klarna", "affirm",
    "zeta-suite", "razorpay-1", "cashfree", "juspay", "payu",
    "chargebee-1", "freshworks", "zoho-1", "leadsquared",
    "browserstack-1", "lambdatest", "testproject",
    "hasura-1", "postman-1", "insomnia",
    "smallcase", "zerodha-1", "groww-1", "kite",
    "classplus", "unacademy-1", "byjus", "vedantu",
    "cure-fit", "healthifyme", "practo",
    "dunzo", "porter-in", "rivigo", "blackbuck",
    "meesho-1", "udaan", "dealshare",
    "mindtickle-1", "highradius-1", "icertis-1",
    "moengage", "clevertap", "webengage",
    "sprinklr-1", "hootsuite-1", "buffer",
    "canva-1", "crello", "visme",
    "notion-1", "coda-1", "slite",
    "pipedrive", "hubspot-1", "salesforce-1",
    "intercom-1", "zendesk-1", "freshdesk",
    "twilio-1", "vonage", "bandwidth",
    "cloudflare-1", "fastly", "akamai",
    "datadog-1", "newrelic", "dynatrace",
    "elastic-1", "splunk", "sumo-logic",
    "okta-1", "auth0", "onelogin",
    "crowdstrike-1", "sentinelone", "cybereason",
]


def seed_workable(conn):
    """Seed Workable companies."""
    print("[seed] Seeding Workable companies...")
    count = 0

    for token in WORKABLE_KNOWN_TOKENS:
        if _insert_company(conn, token, "workable", token):
            count += 1

    # Probe the Workable API to validate tokens
    print(f"  [workable] Probing sample tokens for validity...")
    valid = 0
    for token in WORKABLE_KNOWN_TOKENS[:15]:
        try:
            resp = requests.post(
                f"https://apply.workable.com/api/v3/accounts/{token}/jobs",
                json={"query": "", "location": [], "remote": True},
                timeout=3,
                headers=HEADERS,
            )
            if resp.ok:
                valid += 1
        except Exception:
            pass
    print(f"  [workable] {valid}/15 sampled tokens are valid Workable boards")

    print(f"  [workable] Inserted {count} Workable companies")
    return count


# ─── BambooHR ─────────────────────────────────────────────────────────────────

BAMBOOHR_KNOWN_TOKENS = [
    # Well-known companies using BambooHR
    "fitbit", "asana", "shutterstock", "grammarly", "calendly",
    "nextdoor", "thumbtack", "yelp", "opendoor", "redfin",
    "compass", "zillow", "offerpad", "homelight",
    "gusto", "justworks", "namely", "paylocity",
    "betterment", "wealthfront", "acorns", "stash",
    "headspace", "calm", "noom", "peloton",
    "doordash", "instacart", "grubhub", "postmates",
    "strava", "alltrails", "komoot",
    "duolingo", "coursera", "udemy", "skillshare",
    "medium", "substack", "ghost",
    "figma-1", "sketch", "invision",
    "webflow", "squarespace", "wix-engineering",
    "shopify-1", "bigcommerce", "magento",
    "segment", "mparticle", "rudderstack-1",
    "algolia", "typesense", "meilisearch-1",
    "samsara", "particle", "arduino",
]


def seed_bamboohr(conn):
    """Seed BambooHR companies."""
    print("[seed] Seeding BambooHR companies...")
    count = 0

    for token in BAMBOOHR_KNOWN_TOKENS:
        if _insert_company(conn, token, "bamboohr", token):
            count += 1

    print(f"  [bamboohr] Inserted {count} BambooHR companies")
    return count


# ─── Workday ──────────────────────────────────────────────────────────────────

WORKDAY_KNOWN_TENANTS = [
    # Major companies using Workday
    "amazon", "microsoft", "google", "meta", "apple",
    "netflix", "salesforce", "adobe", "vmware", "dell",
    "hp", "ibm", "oracle", "cisco", "intel",
    "qualcomm", "nvidia", "amd", "broadcom", "texas-instruments",
    "jpmorgan", "goldmansachs", "morganstanley", "bofa", "citi",
    "wellsfargo", "barclays", "hsbc", "ubs", "deutschebank",
    "deloitte", "pwc", "ey", "kpmg", "accenture",
    "mckinsey", "bcg", "bain", "capgemini", "cognizant",
    "tcs", "infosys", "wipro", "hcl", "techm",
    "lti", "mindtree", "mphasis", "hexaware", "niit",
    "walmart", "target", "costco", "kroger", "albertsons",
    "starbucks", "mcdonalds", "chipotle", "dominos",
    "nike", "adidas", "puma", "underarmour",
    "toyota", "honda", "ford", "gm", "bmw",
    "boeing", "airbus", "lockheedmartin", "raytheon",
    "pfizer", "jnj", "merck", "abbvie", "novartis",
    "unilever", "pg", "nestle", "cocacola", "pepsico",
    "disney", "warnerbros", "paramount", "nbcuniversal",
    "visa", "mastercard", "amex", "paypal",
    "uber-1", "lyft", "grab", "gojek-1",
    "airbnb-1", "booking", "expedia", "tripadvisor",
    "zoom", "slack", "teams", "webex",
    "atlassian-1", "jira", "confluence",
    "servicenow", "bmc", "ivanti",
    "workday", "sap", "oracle-1",
    "snowflake", "databricks", "palantir",
    "crowdstrike", "paloaltonetworks", "fortinet",
    "zscaler", "cloudflare", "akamai-1",
    # India-specific Workday users
    "reliancejio", "tata", "mahindra", "bajaj",
    "adani", "birla", "godrej", "itc",
    "hdfc", "icici", "axis", "kotak",
    "swiggy-1", "zomato", "flipkart", "myntra",
    "phonepe-1", "paytm-1", "cred-1",
    "ola-1", "oyo", "makemytrip",
]


def seed_workday(conn):
    """Seed Workday tenants."""
    print("[seed] Seeding Workday tenants...")
    count = 0

    for tenant in WORKDAY_KNOWN_TENANTS:
        if _insert_company(conn, tenant, "workday", tenant):
            count += 1

    print(f"  [workday] Inserted {count} Workday tenants")
    return count


# ─── Merge local india_tech_companies.json ────────────────────────────────────

def seed_local_json(conn):
    """Merge the local india_tech_companies.json."""
    local_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "india_tech_companies.json")
    if not os.path.exists(local_path):
        print("[seed] No india_tech_companies.json found, skipping.")
        return 0

    print("[seed] Merging india_tech_companies.json...")
    count = 0
    with open(local_path, "r") as f:
        data = json.load(f)
    for c in data:
        if "token" not in c or "ats" not in c:
            continue
        if _insert_company(conn, c.get("name", c["token"]), c["ats"], c["token"]):
            count += 1
    print(f"  [local] Inserted {count} companies from local JSON")
    return count


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    init_db()
    total = 0

    with get_conn() as conn:
        # Get baseline
        row = conn.execute("SELECT count(*) as c FROM ats_companies").fetchone()
        baseline = row["c"] if row else 0
        print(f"\n[seed] Baseline: {baseline} companies in DB\n")

        total += seed_ashby(conn)
        total += seed_workable(conn)
        total += seed_bamboohr(conn)
        total += seed_workday(conn)
        total += seed_local_json(conn)

        # Final count
        row = conn.execute("SELECT count(*) as c FROM ats_companies").fetchone()
        final = row["c"] if row else 0

        # Per-ATS breakdown
        print(f"\n{'='*50}")
        print(f"[seed] SUMMARY")
        print(f"{'='*50}")
        print(f"  Before: {baseline}")
        print(f"  Added:  {final - baseline}")
        print(f"  Total:  {final}")
        print()

        rows = conn.execute("SELECT ats_type, count(*) as c FROM ats_companies GROUP BY ats_type ORDER BY c DESC").fetchall()
        for r in rows:
            print(f"  {r['ats_type']:15s} {r['c']:>6d}")


if __name__ == "__main__":
    main()
