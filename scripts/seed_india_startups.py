"""
seed_india_startups.py — Discover Indian startups and detect their ATS.

Strategy:
1. Start with curated lists of Indian startups from public directories.
2. For each company, probe known ATS API endpoints to detect their provider.
3. If an ATS is found, add to ats_companies with the correct token.
4. If no ATS is found, add to companies_custom for later career page crawling.

This script uses only public, freely accessible data.
"""

import json
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
from services.db import get_conn, init_db

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
}

# ─── Curated India Startup Lists ──────────────────────────────────────────────
# These are real companies from the Indian startup ecosystem.
# Organized by category for better coverage of the "hidden job market".

INDIA_STARTUPS = [
    # ── Fintech ──
    {"name": "Slice", "domain": "sliceit.com"},
    {"name": "Jupiter", "domain": "jupiter.money"},
    {"name": "Fi Money", "domain": "fi.money"},
    {"name": "Niyo", "domain": "goniyo.com"},
    {"name": "Open Financial", "domain": "open.money"},
    {"name": "Lendingkart", "domain": "lendingkart.com"},
    {"name": "MoneyTap", "domain": "moneytap.com"},
    {"name": "KreditBee", "domain": "kreditbee.in"},
    {"name": "Rupeek", "domain": "rupeek.com"},
    {"name": "Kuvera", "domain": "kuvera.in"},
    {"name": "Scripbox", "domain": "scripbox.com"},
    {"name": "INDmoney", "domain": "indmoney.com"},
    {"name": "Fyle", "domain": "fylehq.com"},
    {"name": "Recko", "domain": "recko.io"},
    {"name": "Decentro", "domain": "decentro.tech"},
    {"name": "Setu", "domain": "setu.co"},
    {"name": "M2P Fintech", "domain": "m2pfintech.com"},
    {"name": "Perfios", "domain": "perfios.com"},
    {"name": "Signzy", "domain": "signzy.com"},
    {"name": "Finbox", "domain": "finbox.in"},
    {"name": "ToneTag", "domain": "tonetag.com"},
    {"name": "Digio", "domain": "digio.in"},
    {"name": "Mswipe", "domain": "mswipe.com"},
    {"name": "NiYO Solutions", "domain": "goniyo.com"},
    {"name": "ZestMoney", "domain": "zestmoney.in"},
    {"name": "MoneyView", "domain": "moneyview.in"},
    {"name": "CashE", "domain": "cashe.co.in"},
    {"name": "EarlySalary", "domain": "earlysalary.com"},
    {"name": "Stashfin", "domain": "stashfin.com"},
    {"name": "Kissht", "domain": "kissht.com"},

    # ── SaaS / B2B ──
    {"name": "Freshworks", "domain": "freshworks.com"},
    {"name": "Zoho", "domain": "zoho.com"},
    {"name": "Chargebee", "domain": "chargebee.com"},
    {"name": "Clevertap", "domain": "clevertap.com"},
    {"name": "MoEngage", "domain": "moengage.com"},
    {"name": "WebEngage", "domain": "webengage.com"},
    {"name": "Haptik", "domain": "haptik.ai"},
    {"name": "Yellow.ai", "domain": "yellow.ai"},
    {"name": "Gupshup", "domain": "gupshup.io"},
    {"name": "Whatfix", "domain": "whatfix.com"},
    {"name": "Wingify", "domain": "wingify.com"},
    {"name": "Capillary Tech", "domain": "capillarytech.com"},
    {"name": "CleverX", "domain": "cleverx.com"},
    {"name": "Darwinbox", "domain": "darwinbox.com"},
    {"name": "Keka HR", "domain": "keka.com"},
    {"name": "GreytHR", "domain": "greythr.com"},
    {"name": "ZingHR", "domain": "zinghr.com"},
    {"name": "PeopleStrong", "domain": "peoplestrong.com"},
    {"name": "sumHR", "domain": "sumhr.com"},
    {"name": "Pocket HR", "domain": "pockethrms.com"},
    {"name": "Qandle", "domain": "qandle.com"},
    {"name": "Hiver", "domain": "hiverhq.com"},
    {"name": "Helpshift", "domain": "helpshift.com"},
    {"name": "Eka Software", "domain": "eka1.com"},
    {"name": "Kovai.co", "domain": "kovai.co"},
    {"name": "Kissflow", "domain": "kissflow.com"},
    {"name": "Tally Solutions", "domain": "tallysolutions.com"},
    {"name": "Zetwerk", "domain": "zetwerk.com"},
    {"name": "Moglix", "domain": "moglix.com"},
    {"name": "Bizongo", "domain": "bizongo.com"},
    {"name": "OfBusiness", "domain": "ofbusiness.com"},
    {"name": "Udaan", "domain": "udaan.com"},
    {"name": "DealShare", "domain": "dealshare.in"},
    {"name": "ElasticRun", "domain": "elasticrun.in"},
    {"name": "Shiprocket", "domain": "shiprocket.in"},
    {"name": "Delhivery", "domain": "delhivery.com"},
    {"name": "Ecom Express", "domain": "ecomexpress.in"},
    {"name": "Shadowfax", "domain": "shadowfax.in"},
    {"name": "Loadshare", "domain": "loadshare.net"},
    {"name": "Locus", "domain": "locus.sh"},
    {"name": "FarEye", "domain": "fareye.com"},
    {"name": "LogiNext", "domain": "loginext.com"},

    # ── Edtech ──
    {"name": "Physics Wallah", "domain": "physicswallah.live"},
    {"name": "Scaler", "domain": "scaler.com"},
    {"name": "Coding Ninjas", "domain": "codingninjas.com"},
    {"name": "Newton School", "domain": "newtonschool.co"},
    {"name": "Masai School", "domain": "masaischool.com"},
    {"name": "AlmaBetter", "domain": "almabetter.com"},
    {"name": "Cuemath", "domain": "cuemath.com"},
    {"name": "Toppr", "domain": "toppr.com"},
    {"name": "Doubtnut", "domain": "doubtnut.com"},
    {"name": "Teachmint", "domain": "teachmint.com"},
    {"name": "Classplus", "domain": "classplusapp.com"},
    {"name": "Testbook", "domain": "testbook.com"},
    {"name": "Embibe", "domain": "embibe.com"},
    {"name": "Eruditus", "domain": "eruditus.com"},
    {"name": "UpGrad", "domain": "upgrad.com"},
    {"name": "Great Learning", "domain": "greatlearning.in"},
    {"name": "Simplilearn", "domain": "simplilearn.com"},
    {"name": "Intellipaat", "domain": "intellipaat.com"},

    # ── Healthtech ──
    {"name": "Practo", "domain": "practo.com"},
    {"name": "PharmEasy", "domain": "pharmeasy.in"},
    {"name": "1mg (Tata Health)", "domain": "1mg.com"},
    {"name": "Netmeds", "domain": "netmeds.com"},
    {"name": "MediBuddy", "domain": "medibuddy.in"},
    {"name": "mFine", "domain": "mfine.co"},
    {"name": "Healthifyme", "domain": "healthifyme.com"},
    {"name": "CureFit", "domain": "curefit.com"},
    {"name": "Portea Medical", "domain": "portea.com"},
    {"name": "Pristyn Care", "domain": "pristyncare.com"},
    {"name": "Innovaccer", "domain": "innovaccer.com"},
    {"name": "Niramai", "domain": "niramai.com"},
    {"name": "Dozee", "domain": "dozee.io"},
    {"name": "Qure.ai", "domain": "qure.ai"},

    # ── AI / ML / Deep Tech ──
    {"name": "Fractal Analytics", "domain": "fractal.ai"},
    {"name": "Mu Sigma", "domain": "mu-sigma.com"},
    {"name": "Tiger Analytics", "domain": "tigeranalytics.com"},
    {"name": "Sigmoid", "domain": "sigmoid.com"},
    {"name": "Manthan", "domain": "manthan.com"},
    {"name": "ThoughtSpot", "domain": "thoughtspot.com"},
    {"name": "Hasura", "domain": "hasura.io"},
    {"name": "Postman", "domain": "postman.com"},
    {"name": "BrowserStack", "domain": "browserstack.com"},
    {"name": "LambdaTest", "domain": "lambdatest.com"},
    {"name": "Druva", "domain": "druva.com"},
    {"name": "Icertis", "domain": "icertis.com"},
    {"name": "HighRadius", "domain": "highradius.com"},
    {"name": "Zenoti", "domain": "zenoti.com"},
    {"name": "MindTickle", "domain": "mindtickle.com"},
    {"name": "Uniphore", "domain": "uniphore.com"},
    {"name": "SigTuple", "domain": "sigtuple.com"},
    {"name": "Mad Street Den", "domain": "madstreetden.com"},
    {"name": "Observe.AI", "domain": "observe.ai"},
    {"name": "Vernacular.ai", "domain": "vernacular.ai"},
    {"name": "Niki.ai", "domain": "niki.ai"},
    {"name": "Arya.ai", "domain": "arya.ai"},
    {"name": "Fluid AI", "domain": "fluid.ai"},
    {"name": "Rephrase.ai", "domain": "rephrase.ai"},
    {"name": "Gan.ai", "domain": "gan.ai"},
    {"name": "Sarvam AI", "domain": "sarvam.ai"},
    {"name": "Krutrim", "domain": "krutrim.com"},
    {"name": "Ola Krutrim", "domain": "olakrutrim.com"},

    # ── Consumer / D2C ──
    {"name": "Nykaa", "domain": "nykaa.com"},
    {"name": "Mamaearth", "domain": "mamaearth.in"},
    {"name": "Sugar Cosmetics", "domain": "sugarcosmetics.com"},
    {"name": "boAt", "domain": "boat-lifestyle.com"},
    {"name": "Noise", "domain": "gonoise.com"},
    {"name": "Fire-Boltt", "domain": "fire-boltt.com"},
    {"name": "Lenskart", "domain": "lenskart.com"},
    {"name": "Pepperfry", "domain": "pepperfry.com"},
    {"name": "Urban Ladder", "domain": "urbanladder.com"},
    {"name": "Dunzo", "domain": "dunzo.com"},
    {"name": "BigBasket", "domain": "bigbasket.com"},
    {"name": "BlinkIt", "domain": "blinkit.com"},
    {"name": "Zepto", "domain": "zeptonow.com"},
    {"name": "Country Delight", "domain": "countrydelight.in"},
    {"name": "Milkbasket", "domain": "milkbasket.com"},
    {"name": "Dailyhunt", "domain": "dailyhunt.in"},
    {"name": "ShareChat", "domain": "sharechat.com"},
    {"name": "Koo", "domain": "kooapp.com"},

    # ── Mobility / EV ──
    {"name": "Ather Energy", "domain": "atherenergy.com"},
    {"name": "Ola Electric", "domain": "olaelectric.com"},
    {"name": "Bounce", "domain": "bounceshare.com"},
    {"name": "Yulu", "domain": "yulu.bike"},
    {"name": "Rapido", "domain": "rapido.bike"},
    {"name": "BluSmart", "domain": "blusmart.in"},
    {"name": "Micelio", "domain": "micelio.com"},
    {"name": "Simple Energy", "domain": "simpleenergy.in"},
    {"name": "Euler Motors", "domain": "eulermotors.com"},
    {"name": "Log9 Materials", "domain": "log9materials.com"},

    # ── Proptech / Real Estate ──
    {"name": "NoBroker", "domain": "nobroker.in"},
    {"name": "Housing.com", "domain": "housing.com"},
    {"name": "Magicbricks", "domain": "magicbricks.com"},
    {"name": "Square Yards", "domain": "squareyards.com"},
    {"name": "Stanza Living", "domain": "stanzaliving.com"},
    {"name": "Nestaway", "domain": "nestaway.com"},
    {"name": "Colive", "domain": "colive.com"},

    # ── Gaming ──
    {"name": "Games24x7", "domain": "games24x7.com"},
    {"name": "MPL", "domain": "mpl.live"},
    {"name": "WinZO", "domain": "winzogames.com"},
    {"name": "Ludo King (Gametion)", "domain": "gametion.com"},
    {"name": "Nazara Technologies", "domain": "nazara.com"},
    {"name": "SuperGaming", "domain": "supergaming.com"},

    # ── Agritech ──
    {"name": "Ninjacart", "domain": "ninjacart.com"},
    {"name": "DeHaat", "domain": "dehaat.com"},
    {"name": "CropIn", "domain": "cropin.com"},
    {"name": "Intello Labs", "domain": "intello.com"},
    {"name": "Bijak", "domain": "bijak.in"},
    {"name": "AgroStar", "domain": "agrostar.in"},

    # ── Dev Tools / Infra ──
    {"name": "Razorpay", "domain": "razorpay.com"},
    {"name": "Cashfree", "domain": "cashfree.com"},
    {"name": "Juspay", "domain": "juspay.in"},
    {"name": "PayU", "domain": "payu.in"},
    {"name": "InfraCloud", "domain": "infracloud.io"},
    {"name": "Appsmith", "domain": "appsmith.com"},
    {"name": "ToolJet", "domain": "tooljet.com"},
    {"name": "Nhost", "domain": "nhost.io"},
    {"name": "Hyperswitch", "domain": "hyperswitch.io"},
    {"name": "Permit.io", "domain": "permit.io"},
    {"name": "Keploy", "domain": "keploy.io"},
    {"name": "DevRev", "domain": "devrev.ai"},
    {"name": "Codesandbox India", "domain": "codesandbox.io"},
    {"name": "Plane", "domain": "plane.so"},
    {"name": "Hoppscotch", "domain": "hoppscotch.io"},
    {"name": "Amplication", "domain": "amplication.com"},
    {"name": "Lago", "domain": "getlago.com"},

    # ── Cybersecurity ──
    {"name": "TAC Security", "domain": "tacsecurity.com"},
    {"name": "Lucideus (SAFE Security)", "domain": "safe.security"},
    {"name": "InstaSafe", "domain": "instasafe.com"},
    {"name": "Securden", "domain": "securden.com"},
    {"name": "CloudSEK", "domain": "cloudsek.com"},
    {"name": "Sequretek", "domain": "sequretek.com"},

    # ── Consulting / IT Services (lesser-known) ──
    {"name": "ThoughtWorks India", "domain": "thoughtworks.com"},
    {"name": "Publicis Sapient", "domain": "publicissapient.com"},
    {"name": "Nagarro", "domain": "nagarro.com"},
    {"name": "Xoriant", "domain": "xoriant.com"},
    {"name": "Cyient", "domain": "cyient.com"},
    {"name": "KPIT Technologies", "domain": "kpit.com"},
    {"name": "Persistent Systems", "domain": "persistent.com"},
    {"name": "Zensar Technologies", "domain": "zensar.com"},
    {"name": "Birlasoft", "domain": "birlasoft.com"},
    {"name": "Sonata Software", "domain": "sonata-software.com"},
    {"name": "Coforge", "domain": "coforge.com"},
    {"name": "NIIT Technologies", "domain": "niit-tech.com"},
    {"name": "Mphasis", "domain": "mphasis.com"},
    {"name": "L&T Infotech", "domain": "lntinfotech.com"},
    {"name": "Sasken Technologies", "domain": "sasken.com"},
    {"name": "Impetus Technologies", "domain": "impetus.com"},
    {"name": "TO THE NEW", "domain": "tothenew.com"},
    {"name": "Srijan Technologies", "domain": "srijan.net"},
    {"name": "GeekyAnts", "domain": "geekyants.com"},
    {"name": "HashedIn by Deloitte", "domain": "hashedin.com"},
    {"name": "Coditas", "domain": "coditas.com"},
    {"name": "QBurst", "domain": "qburst.com"},
    {"name": "Valuebound", "domain": "valuebound.com"},
    {"name": "Axelerant", "domain": "axelerant.com"},
    {"name": "ColoredCow", "domain": "coloredcow.com"},
    {"name": "Qxf2 Services", "domain": "qxf2.com"},
]


# ─── ATS Detection ───────────────────────────────────────────────────────────

def detect_ats_for_domain(name: str, domain: str) -> dict | None:
    """
    Probe known ATS API endpoints to detect what ATS a company uses.
    Returns {"ats_type": ..., "token": ...} or None.
    """
    # Extract the slug from the domain (e.g., razorpay.com → razorpay)
    slug = domain.split(".")[0].lower().replace("-", "").replace("_", "")
    # Also try with hyphens
    slug_hyphen = domain.split(".")[0].lower()

    candidates = [slug, slug_hyphen, name.lower().replace(" ", ""), name.lower().replace(" ", "-")]
    # Remove duplicates while preserving order
    seen = set()
    unique_candidates = []
    for c in candidates:
        if c not in seen:
            seen.add(c)
            unique_candidates.append(c)

    for token in unique_candidates:
        # Greenhouse
        try:
            resp = requests.get(
                f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs",
                timeout=3,
                headers=HEADERS,
            )
            if resp.status_code == 200:
                data = resp.json()
                if "jobs" in data:
                    return {"ats_type": "greenhouse", "token": token}
        except Exception:
            pass

        # Lever
        try:
            resp = requests.get(
                f"https://api.lever.co/v0/postings/{token}?mode=json",
                timeout=3,
                headers=HEADERS,
            )
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list):
                    return {"ats_type": "lever", "token": token}
        except Exception:
            pass

        # Ashby
        try:
            resp = requests.get(
                f"https://api.ashbyhq.com/posting-api/job-board/{token}",
                timeout=3,
                headers=HEADERS,
            )
            if resp.status_code == 200:
                data = resp.json()
                if "jobs" in data:
                    return {"ats_type": "ashby", "token": token}
        except Exception:
            pass

        # Workable
        try:
            resp = requests.post(
                f"https://apply.workable.com/api/v3/accounts/{token}/jobs",
                json={"query": "", "location": [], "remote": True},
                timeout=3,
                headers=HEADERS,
            )
            if resp.status_code == 200:
                return {"ats_type": "workable", "token": token}
        except Exception:
            pass

    return None


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    init_db()

    # Ensure companies_custom table exists
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS companies_custom (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                domain TEXT UNIQUE NOT NULL,
                career_url TEXT,
                ats_detected TEXT,
                last_checked TEXT,
                status TEXT DEFAULT 'pending'
            )
        """)

    total_ats = 0
    total_custom = 0
    ats_breakdown = {}

    logger.info(f"[seed_india] Processing {len(INDIA_STARTUPS)} Indian startups...")

    def process_company(company):
        name = company["name"]
        domain = company["domain"]
        result = detect_ats_for_domain(name, domain)
        return name, domain, result

    # Use thread pool for concurrent ATS detection
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(process_company, c): c for c in INDIA_STARTUPS}

        for future in as_completed(futures, timeout=300):
            try:
                name, domain, result = future.result()

                with get_conn() as conn:
                    if result:
                        ats_type = result["ats_type"]
                        token = result["token"]
                        try:
                            conn.execute(
                                "INSERT OR IGNORE INTO ats_companies (name, ats_type, token) VALUES (?, ?, ?)",
                                (name, ats_type, token),
                            )
                            ats_breakdown[ats_type] = ats_breakdown.get(ats_type, 0) + 1
                            logger.info(f"  ✓ {name} → {ats_type} (token: {token})")
                        except sqlite3.Error:
                            pass
                    else:
                        try:
                            conn.execute(
                                "INSERT OR IGNORE INTO companies_custom (name, domain, status) VALUES (?, ?, 'pending')",
                                (name, domain),
                            )
                            logger.info(f"  ○ {name} → custom (no ATS detected)")
                        except sqlite3.Error:
                            pass
            except Exception as e:
                logger.error(f"  ✗ Error: {e}")

    # Final summary
    with get_conn() as conn:
        row = conn.execute("SELECT count(*) as c FROM ats_companies").fetchone()
        total_ats = row["c"] if row else 0
        row = conn.execute("SELECT count(*) as c FROM companies_custom").fetchone()
        total_custom = row["c"] if row else 0

    print(f"\n{'='*50}")
    print(f"[seed_india] SUMMARY")
    print(f"{'='*50}")
    print(f"  ATS companies total: {total_ats}")
    print(f"  Custom companies:    {total_custom}")
    print(f"  ATS breakdown:")
    for ats, count in sorted(ats_breakdown.items(), key=lambda x: -x[1]):
        print(f"    {ats:15s} {count:>4d}")
    print()


if __name__ == "__main__":
    main()
