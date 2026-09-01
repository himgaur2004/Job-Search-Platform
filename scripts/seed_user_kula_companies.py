"""
seed_user_kula_companies.py — Seed user-provided Kula ATS company list into ats_companies.
"""

import logging
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from services.db import get_conn

logger = logging.getLogger(__name__)

KULA_USER_TABLE = [
    ("AppsForBharat", "kula", "appsforbharat"),
    ("SaaS Labs", "kula", "saas-labs"),
    ("GreyLabs AI", "kula", "greylabs"),
    ("Digantara", "kula", "digantara"),
    ("Sarvam AI", "kula", "sarvam-ai"),
    ("Uniqode", "kula", "uniqode"),
    ("Plum", "kula", "plum"),
    ("Rocketlane", "kula", "rocketlane"),
    ("Zamp AI", "kula", "zamp-ai"),
    ("CleverTap", "kula", "clevertap"),
    ("ACKO", "kula", "acko"),
    ("Aramya", "kula", "aramya"),
    ("Bright Money", "kula", "brightmoney"),
    ("Avoma", "kula", "avoma"),
]


def seed_kula_table():
    inserted = 0
    with get_conn() as conn:
        for name, ats_type, token in KULA_USER_TABLE:
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

    logger.info(f"[seed_user_kula_companies] Successfully seeded {inserted} Kula ATS company tokens into DB!")
    print(f"Successfully seeded {inserted} Kula ATS company tokens into database!")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    seed_kula_table()
