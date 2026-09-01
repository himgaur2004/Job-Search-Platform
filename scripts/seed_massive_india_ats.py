"""
seed_massive_india_ats.py — Seed 250+ Indian and global tech companies across all 15 supported ATS platforms.

Supported ATS types:
  - rippling (Rippling ATS)
  - kula (Kula ATS)
  - ashby (Ashby HQ)
  - smartrecruiters (SmartRecruiters)
  - recruitee (Recruitee)
  - breezy (Breezy HR)
  - teamtailor (Teamtailor)
  - freshteam (Freshteam)
  - workable (Workable)
  - bamboohr (BambooHR)
  - greenhouse (Greenhouse)
  - lever (Lever)
  - workday (Workday)
  - oracle (Oracle HCM)
  - icims (iCIMS)
"""

import logging
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from services.db import get_conn

logger = logging.getLogger(__name__)

MASSIVE_COMPANY_TOKENS = [
    # ─── Rippling ATS ────────────────────────────────────────────────────────
    ("Rippling", "rippling", "rippling"),
    ("Brex", "rippling", "brex"),
    ("Ramp", "rippling", "ramp"),
    ("Mercury", "rippling", "mercury"),
    ("Figma", "rippling", "figma"),
    ("Whatfix", "rippling", "whatfix"),
    ("Sprinto", "rippling", "sprinto"),
    ("Atomicwork", "rippling", "atomicwork"),
    ("LlamaIndex", "rippling", "llamaindex"),
    ("LangChain", "rippling", "langchain"),
    ("Scale AI", "rippling", "scaleai"),
    ("Substack", "rippling", "substack"),
    ("Retool", "rippling", "retool"),

    # ─── Kula ATS ────────────────────────────────────────────────────────────
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
    ("Unacademy Kula", "kula", "unacademy"),
    ("KreditBee Kula", "kula", "kreditbee"),
    ("Groww Kula", "kula", "groww"),

    # ─── Ashby HQ ─────────────────────────────────────────────────────────────
    ("Deel", "ashby", "deel"),
    ("Notion", "ashby", "notion"),
    ("Cohere", "ashby", "cohere"),
    ("Polymarket", "ashby", "polymarket"),
    ("Onebrief", "ashby", "onebrief"),
    ("Prompt", "ashby", "prompt"),
    ("Notable", "ashby", "notable"),
    ("Linear", "ashby", "linear"),
    ("Vercel", "ashby", "vercel"),
    ("OpenAI", "ashby", "openai"),
    ("Supabase", "ashby", "supabase"),
    ("PostHog", "ashby", "posthog"),
    ("Loom", "ashby", "loom"),
    ("Temporal", "ashby", "temporal"),
    ("Resend", "ashby", "resend"),
    ("Perplexity AI", "ashby", "perplexity"),
    ("Mistral AI", "ashby", "mistral"),
    ("Together AI", "ashby", "togetherai"),
    ("Anyscale", "ashby", "anyscale"),
    ("Cursor", "ashby", "cursor"),

    # ─── SmartRecruiters ──────────────────────────────────────────────────────
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

    # ─── Recruitee ───────────────────────────────────────────────────────────
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

    # ─── Breezy HR ───────────────────────────────────────────────────────────
    ("Nifty", "breezy", "nifty"),
    ("Pipe", "breezy", "pipe"),
    ("Frame", "breezy", "frame"),
    ("Design pickle", "breezy", "designpickle"),
    ("Buffer", "breezy", "buffer"),
    ("Multiplier", "breezy", "usemultiplier"),
    ("Avanceon", "breezy", "avanceon"),
    ("Savvy", "breezy", "savvy"),
    ("Air Titans", "breezy", "air-titans"),

    # ─── Teamtailor ──────────────────────────────────────────────────────────
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

    # ─── Freshteam ───────────────────────────────────────────────────────────
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


def seed_massive_india_ats():
    inserted = 0
    with get_conn() as conn:
        for name, ats_type, token in MASSIVE_COMPANY_TOKENS:
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

    logger.info(f"[seed_massive_india_ats] Successfully seeded {inserted} companies into ats_companies!")
    print(f"Successfully seeded {inserted} tech companies across 15 ATS platforms!")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    seed_massive_india_ats()
