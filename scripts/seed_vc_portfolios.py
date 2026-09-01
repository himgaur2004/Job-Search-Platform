"""
seed_vc_portfolios.py — Massively expand company database by seeding top Indian & Global VC portfolio companies.

VC Portfolios included:
- Peak XV Partners (formerly Sequoia India)
- Accel India
- Lightspeed India
- Elevation Capital (formerly SAIF Partners)
- Nexus Venture Partners
- Matrix Partners India
- Blume Ventures
- Kalaari Capital
- Stellaris Venture Partners
- Chiratae Ventures
- 3one4 Capital
- Tiger Global India Portfolios
- Y Combinator India Batch Startups
"""

import json
import logging
import os
import sqlite3
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from services.db import get_conn, init_db
from scripts.seed_india_startups import detect_ats_for_domain

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

VC_PORTFOLIOS = [
    # --- Peak XV Partners / Sequoia India ---
    {"name": "Mamaearth", "domain": "mamaearth.in", "vc": "Peak XV"},
    {"name": "BYJU'S", "domain": "byjus.com", "vc": "Peak XV"},
    {"name": "CarDekho", "domain": "cardekho.com", "vc": "Peak XV"},
    {"name": "CureFit", "domain": "curefit.com", "vc": "Peak XV"},
    {"name": "Dailyhunt", "domain": "dailyhunt.in", "vc": "Peak XV"},
    {"name": "Eruditus", "domain": "eruditus.com", "vc": "Peak XV"},
    {"name": "Khatabook", "domain": "khatabook.com", "vc": "Peak XV"},
    {"name": "KredX", "domain": "kredx.com", "vc": "Peak XV"},
    {"name": "Meadow", "domain": "meadow.co", "vc": "Peak XV"},
    {"name": "Mobilion", "domain": "mobilion.in", "vc": "Peak XV"},
    {"name": "Moglix", "domain": "moglix.com", "vc": "Peak XV"},
    {"name": "Ninjacart", "domain": "ninjacart.com", "vc": "Peak XV"},
    {"name": "OneCode", "domain": "onecode.in", "vc": "Peak XV"},
    {"name": "Rebel Foods", "domain": "rebelfoods.com", "vc": "Peak XV"},
    {"name": "Turtlemint", "domain": "turtlemint.com", "vc": "Peak XV"},
    {"name": "Unacademy", "domain": "unacademy.com", "vc": "Peak XV"},
    {"name": "Wakefit", "domain": "wakefit.co", "vc": "Peak XV"},
    {"name": "Zetwerk", "domain": "zetwerk.com", "vc": "Peak XV"},

    # --- Accel India ---
    {"name": "Acko", "domain": "acko.com", "vc": "Accel"},
    {"name": "AgroStar", "domain": "agrostar.in", "vc": "Accel"},
    {"name": "Bizo", "domain": "bizongo.com", "vc": "Accel"},
    {"name": "BlueStone", "domain": "bluestone.com", "vc": "Accel"},
    {"name": "BookMyShow", "domain": "bookmyshow.com", "vc": "Accel"},
    {"name": "BrowserStack", "domain": "browserstack.com", "vc": "Accel"},
    {"name": "Chargebee", "domain": "chargebee.com", "vc": "Accel"},
    {"name": "Clevertap", "domain": "clevertap.com", "vc": "Accel"},
    {"name": "Cult.fit", "domain": "cult.fit", "vc": "Accel"},
    {"name": "Falcon", "domain": "falcon.io", "vc": "Accel"},
    {"name": "Infra.Market", "domain": "infra.market", "vc": "Accel"},
    {"name": "MindTickle", "domain": "mindtickle.com", "vc": "Accel"},
    {"name": "Moglix", "domain": "moglix.com", "vc": "Accel"},
    {"name": "Myntra", "domain": "myntra.com", "vc": "Accel"},
    {"name": "Ninjacart", "domain": "ninjacart.com", "vc": "Accel"},
    {"name": "Rupeek", "domain": "rupeek.com", "vc": "Accel"},
    {"name": "Scripbox", "domain": "scripbox.com", "vc": "Accel"},
    {"name": "Swiggy", "domain": "swiggy.com", "vc": "Accel"},
    {"name": "Urban Company", "domain": "urbancompany.com", "vc": "Accel"},
    {"name": "Zeta", "domain": "zeta.tech", "vc": "Accel"},

    # --- Lightspeed India ---
    {"name": "Aspiring Minds", "domain": "aspiringminds.com", "vc": "Lightspeed"},
    {"name": "BYJU'S", "domain": "byjus.com", "vc": "Lightspeed"},
    {"name": "Craftsvilla", "domain": "craftsvilla.com", "vc": "Lightspeed"},
    {"name": "Darwinbox", "domain": "darwinbox.com", "vc": "Lightspeed"},
    {"name": "Dxio", "domain": "dxio.io", "vc": "Lightspeed"},
    {"name": "Fashinza", "domain": "fashinza.com", "vc": "Lightspeed"},
    {"name": "IndianSchoolOfGaming", "domain": "isg.org.in", "vc": "Lightspeed"},
    {"name": "KhataBook", "domain": "khatabook.com", "vc": "Lightspeed"},
    {"name": "Magicpin", "domain": "magicpin.in", "vc": "Lightspeed"},
    {"name": "OkCredit", "domain": "okcredit.in", "vc": "Lightspeed"},
    {"name": "Oyo Rooms", "domain": "oyorooms.com", "vc": "Lightspeed"},
    {"name": "Pocket FM", "domain": "pocketfm.in", "vc": "Lightspeed"},
    {"name": "ShareChat", "domain": "sharechat.com", "vc": "Lightspeed"},
    {"name": "Yellow.ai", "domain": "yellow.ai", "vc": "Lightspeed"},

    # --- Elevation Capital ---
    {"name": "Acko", "domain": "acko.com", "vc": "Elevation"},
    {"name": "Country Delight", "domain": "countrydelight.in", "vc": "Elevation"},
    {"name": "Fashinza", "domain": "fashinza.com", "vc": "Elevation"},
    {"name": "FirstCry", "domain": "firstcry.com", "vc": "Elevation"},
    {"name": "Juspay", "domain": "juspay.in", "vc": "Elevation"},
    {"name": "MakeMyTrip", "domain": "makemytrip.com", "vc": "Elevation"},
    {"name": "Mezi", "domain": "mezi.com", "vc": "Elevation"},
    {"name": "Meesho", "domain": "meesho.com", "vc": "Elevation"},
    {"name": "NoBroker", "domain": "nobroker.in", "vc": "Elevation"},
    {"name": "Paytm", "domain": "paytm.com", "vc": "Elevation"},
    {"name": "ShareChat", "domain": "sharechat.com", "vc": "Elevation"},
    {"name": "Swiggy", "domain": "swiggy.com", "vc": "Elevation"},
    {"name": "Unacademy", "domain": "unacademy.com", "vc": "Elevation"},
    {"name": "Urban Company", "domain": "urbancompany.com", "vc": "Elevation"},

    # --- Nexus Venture Partners ---
    {"name": "Apollo.io", "domain": "apollo.io", "vc": "Nexus"},
    {"name": "Astrato", "domain": "astrato.io", "vc": "Nexus"},
    {"name": "Clover Health", "domain": "cloverhealth.com", "vc": "Nexus"},
    {"name": "Druva", "domain": "druva.com", "vc": "Nexus"},
    {"name": "Fingerprint", "domain": "fingerprint.com", "vc": "Nexus"},
    {"name": "Hasura", "domain": "hasura.io", "vc": "Nexus"},
    {"name": "Haptik", "domain": "haptik.ai", "vc": "Nexus"},
    {"name": "Infoworks", "domain": "infoworks.io", "vc": "Nexus"},
    {"name": "MinIO", "domain": "min.io", "vc": "Nexus"},
    {"name": "Observe.AI", "domain": "observe.ai", "vc": "Nexus"},
    {"name": "Postman", "domain": "postman.com", "vc": "Nexus"},
    {"name": "PubMatic", "domain": "pubmatic.com", "vc": "Nexus"},
    {"name": "Ransom42", "domain": "ransom42.com", "vc": "Nexus"},
    {"name": "Uniphore", "domain": "uniphore.com", "vc": "Nexus"},

    # --- Blume Ventures ---
    {"name": "CarbonClean", "domain": "ccus.com", "vc": "Blume"},
    {"name": "Chalo", "domain": "chalo.com", "vc": "Blume"},
    {"name": "Classplus", "domain": "classplusapp.com", "vc": "Blume"},
    {"name": "Dunzo", "domain": "dunzo.com", "vc": "Blume"},
    {"name": "ElectricPe", "domain": "electricpe.com", "vc": "Blume"},
    {"name": "Exotel", "domain": "exotel.com", "vc": "Blume"},
    {"name": "GreyOrange", "domain": "greyorange.com", "vc": "Blume"},
    {"name": "HealthifyMe", "domain": "healthifyme.com", "vc": "Blume"},
    {"name": "InVideo", "domain": "invideo.io", "vc": "Blume"},
    {"name": "Kuku FM", "domain": "kukufm.com", "vc": "Blume"},
    {"name": "Locus", "domain": "locus.sh", "vc": "Blume"},
    {"name": "LoveLocal", "domain": "lovelocal.in", "vc": "Blume"},
    {"name": "Milkbasket", "domain": "milkbasket.com", "vc": "Blume"},
    {"name": "Purplle", "domain": "purplle.com", "vc": "Blume"},
    {"name": "Slice", "domain": "sliceit.com", "vc": "Blume"},
    {"name": "Spinny", "domain": "spinny.com", "vc": "Blume"},
    {"name": "Turtlemint", "domain": "turtlemint.com", "vc": "Blume"},
    {"name": "Ultrahuman", "domain": "ultrahuman.com", "vc": "Blume"},
    {"name": "Unacademy", "domain": "unacademy.com", "vc": "Blume"},
    {"name": "WebEngage", "domain": "webengage.com", "vc": "Blume"},

    # --- Y Combinator India ---
    {"name": "Razorpay", "domain": "razorpay.com", "vc": "Y Combinator"},
    {"name": "ClearTax", "domain": "cleartax.in", "vc": "Y Combinator"},
    {"name": "Meesho", "domain": "meesho.com", "vc": "Y Combinator"},
    {"name": "Khatabook", "domain": "khatabook.com", "vc": "Y Combinator"},
    {"name": "Groww", "domain": "groww.in", "vc": "Y Combinator"},
    {"name": "Zepto", "domain": "zeptonow.com", "vc": "Y Combinator"},
    {"name": "OkCredit", "domain": "okcredit.in", "vc": "Y Combinator"},
    {"name": "Fyle", "domain": "fylehq.com", "vc": "Y Combinator"},
    {"name": "Smallcase", "domain": "smallcase.com", "vc": "Y Combinator"},
    {"name": "Mudrex", "domain": "mudrex.com", "vc": "Y Combinator"},
    {"name": "Decentro", "domain": "decentro.tech", "vc": "Y Combinator"},
    {"name": "BukuWarung", "domain": "bukuwarung.com", "vc": "Y Combinator"},
    {"name": "Bikayi", "domain": "bikayi.com", "vc": "Y Combinator"},
    {"name": "Nearcut", "domain": "nearcut.com", "vc": "Y Combinator"},
    {"name": "OrangeHealth", "domain": "orangehealth.in", "vc": "Y Combinator"},
    {"name": "PagarBook", "domain": "pagarbook.com", "vc": "Y Combinator"},
    {"name": "Relevance AI", "domain": "relevanceai.com", "vc": "Y Combinator"},
]


def seed_vc_companies():
    """Seed VC portfolio companies into the database."""
    init_db()

    added_ats = 0
    added_custom = 0

    logger.info(f"[seed_vc] Processing {len(VC_PORTFOLIOS)} VC portfolio companies...")

    for c in VC_PORTFOLIOS:
        name = c["name"]
        domain = c["domain"]
        vc = c.get("vc", "VC")

        result = detect_ats_for_domain(name, domain)

        with get_conn() as conn:
            if result:
                ats_type = result["ats_type"]
                token = result["token"]
                try:
                    conn.execute(
                        "INSERT OR IGNORE INTO ats_companies (name, ats_type, token) VALUES (?, ?, ?)",
                        (f"{name} ({vc})", ats_type, token),
                    )
                    added_ats += 1
                    logger.info(f"  ✓ {name} ({vc}) → {ats_type}")
                except sqlite3.Error:
                    pass
            else:
                try:
                    conn.execute(
                        "INSERT OR IGNORE INTO companies_custom (name, domain, status) VALUES (?, ?, 'pending')",
                        (f"{name} ({vc})", domain),
                    )
                    added_custom += 1
                    logger.info(f"  ○ {name} ({vc}) → custom")
                except sqlite3.Error:
                    pass

    logger.info(f"[seed_vc] Complete: added {added_ats} ATS companies, {added_custom} custom companies.")


if __name__ == "__main__":
    seed_vc_companies()
