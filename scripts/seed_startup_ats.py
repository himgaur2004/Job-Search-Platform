"""
seed_startup_ats.py — Expanded company tokens for SmartRecruiters, Recruitee, Breezy HR, Teamtailor, Freshteam, Kula, Ashby, Workable, BambooHR, and Workday.
"""

import logging
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from services.db import get_conn

logger = logging.getLogger(__name__)

EXPANDED_ATS_COMPANIES = [
    # ─── Kula ATS (kula) ──────────────────────────────────────────────────────
    ("Clevertap", "kula", "clevertap"),
    ("Acko", "kula", "acko"),
    ("Plum HQ", "kula", "plumhq"),
    ("Pine Labs", "kula", "pinelabs"),
    ("WebEngage", "kula", "webengage"),
    ("Setu", "kula", "setu"),
    ("Jar", "kula", "jar"),
    ("KredX", "kula", "kredx"),
    ("Kula AI", "kula", "kula"),
    ("Rankviz", "kula", "rankviz-1"),

    # ─── Ashby HQ (ashby) ─────────────────────────────────────────────────────
    ("Deel", "ashby", "deel"),
    ("Notion", "ashby", "notion"),
    ("Cohere", "ashby", "cohere"),
    ("Polymarket", "ashby", "polymarket"),
    ("Onebrief", "ashby", "onebrief"),
    ("Prompt", "ashby", "prompt"),
    ("Notable", "ashby", "notable"),
    ("Ramp", "ashby", "ramp"),
    ("Linear", "ashby", "linear"),
    ("Vercel", "ashby", "vercel"),
    ("OpenAI", "ashby", "openai"),
    ("Scale AI", "ashby", "scaleai"),
    ("Supabase", "ashby", "supabase"),
    ("Retool", "ashby", "retool"),
    ("Figma", "ashby", "figma"),
    ("PostHog", "ashby", "posthog"),
    ("Loom", "ashby", "loom"),
    ("Temporal", "ashby", "temporal"),
    ("Resend", "ashby", "resend"),

    # ─── SmartRecruiters (smartrecruiters) ──────────────────────────────────
    ("Square", "smartrecruiters", "square"),
    ("Visa", "smartrecruiters", "visa"),
    ("Ubisoft", "smartrecruiters", "ubisoft"),
    ("Bosch", "smartrecruiters", "Bosch"),
    ("Volvo", "smartrecruiters", "volvo"),
    ("Publicis Sapient", "smartrecruiters", "PublicisSapient"),
    ("Sephora", "smartrecruiters", "sephora"),
    ("Western Digital", "smartrecruiters", "westerndigital"),
    ("Avery Dennison", "smartrecruiters", "averydennison"),
    ("Skechers", "smartrecruiters", "skechers"),
    ("Block", "smartrecruiters", "block"),
    ("Samsara", "smartrecruiters", "samsara"),
    ("Collibra", "smartrecruiters", "collibra"),
    ("Checkr", "smartrecruiters", "checkr"),
    ("Thoughtworks", "smartrecruiters", "thoughtworks"),
    ("Quantcast", "smartrecruiters", "quantcast"),
    ("Epidemic Sound", "smartrecruiters", "epidemicsound"),
    ("Accor", "smartrecruiters", "accorhotel"),
    ("Solflare", "smartrecruiters", "solflare"),
    ("SOSi", "smartrecruiters", "sosi1"),

    # ─── Recruitee (recruitee) ──────────────────────────────────────────────
    ("Hotjar", "recruitee", "hotjar"),
    ("Bunq", "recruitee", "bunq"),
    ("Mollie", "recruitee", "mollie"),
    ("MessageBird", "recruitee", "messagebird"),
    ("Usabilla", "recruitee", "usabilla"),
    ("TransIP", "recruitee", "transip"),
    ("Sleek", "recruitee", "sleek"),
    ("Leadfeeder", "recruitee", "leadfeeder"),
    ("Spendesk", "recruitee", "spendesk"),
    ("Payload", "recruitee", "payload"),
    ("Tidio", "recruitee", "tidio"),
    ("Prismic", "recruitee", "prismic"),
    ("Drover", "recruitee", "drover"),
    ("Swapcard", "recruitee", "swapcard"),
    ("DevFinders", "recruitee", "devfinders"),
    ("Element Insurance", "recruitee", "elementinsuranceag"),

    # ─── Breezy HR (breezy) ──────────────────────────────────────────────────
    ("Nifty", "breezy", "nifty"),
    ("Pipe", "breezy", "pipe"),
    ("Frame", "breezy", "frame"),
    ("Substack", "breezy", "substack"),
    ("Replit", "breezy", "replit"),
    ("Design pickle", "breezy", "designpickle"),
    ("Buffer", "breezy", "buffer"),
    ("Multiplier", "breezy", "usemultiplier"),
    ("Avanceon", "breezy", "avanceon"),
    ("Savvy", "breezy", "savvy"),
    ("Air Titans", "breezy", "air-titans"),

    # ─── Teamtailor (teamtailor) ─────────────────────────────────────────────
    ("Klarna", "teamtailor", "klarna"),
    ("Spotify", "teamtailor", "spotify"),
    ("Mentimeter", "teamtailor", "mentimeter"),
    ("Soundtrap", "teamtailor", "soundtrap"),
    ("Kry", "teamtailor", "kry"),
    ("Storytel", "teamtailor", "storytel"),
    ("Pleo", "teamtailor", "pleo"),
    ("Truecaller", "teamtailor", "truecaller"),
    ("Boda", "teamtailor", "boda"),
    ("Tibber", "teamtailor", "tibber"),
    ("Citation Group", "teamtailor", "citationgroup"),
    ("Capalo AI", "teamtailor", "capaloai"),
    ("Acumetis", "teamtailor", "acumetis"),

    # ─── Freshteam (freshteam) ───────────────────────────────────────────────
    ("Freshworks", "freshteam", "freshworks"),
    ("Gupshup", "freshteam", "gupshup"),
    ("Chargebee", "freshteam", "chargebee"),
    ("Kissflow", "freshteam", "kissflow"),
    ("Paperflite", "freshteam", "paperflite"),
    ("Hippo Video", "freshteam", "hippovideo"),
    ("VWO", "freshteam", "vwo"),
    ("Simform", "freshteam", "simformsolutions"),
    ("Syfe", "freshteam", "syfe-talent"),
    ("Shorthand", "freshteam", "shorthand"),
]


def seed_startup_ats():
    inserted = 0
    with get_conn() as conn:
        for name, ats_type, token in EXPANDED_ATS_COMPANIES:
            try:
                conn.execute(
                    """
                    INSERT INTO ats_companies (name, ats_type, token, status)
                    VALUES (?, ?, ?, 'active')
                    ON CONFLICT(token) DO UPDATE SET
                        ats_type=excluded.ats_type,
                        name=excluded.name,
                        status='active'
                    """,
                    (name, ats_type, token)
                )
                inserted += 1
            except Exception as e:
                logger.debug(f"Error seeding {name}: {e}")
        conn.commit()

    logger.info(f"[seed_startup_ats] Successfully seeded {inserted} startup ATS tokens!")
    print(f"Successfully seeded {inserted} startup ATS company tokens into database!")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    seed_startup_ats()
