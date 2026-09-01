"""
seed_user_custom_companies.py — Ingest user-provided company list into companies_custom table.
"""

import logging
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from services.db import get_conn

logger = logging.getLogger(__name__)

USER_PROVIDED_COMPANIES = [
    ("AppsForBharat", "https://appsforbharat.com/careers", "Technology"),
    ("Rocketlane", "https://www.rocketlane.com/careers", "SaaS"),
    ("Sarvam AI", "https://sarvam.ai/careers", "AI"),
    ("Plum", "https://www.plumhq.com/careers", "Insurance"),
    ("Multiplier", "https://www.usemultiplier.com/careers", "HR Tech"),
    ("Cover Genius", "https://covergenius.com/careers", "InsurTech"),
    ("Avoma", "https://www.avoma.com/careers", "AI SaaS"),
    ("Vidyard", "https://www.vidyard.com/careers", "SaaS"),
    ("Dapper Labs", "https://www.dapperlabs.com/careers", "Web3"),
    ("Bubble", "https://bubble.io/careers", "Software"),
    ("10x Genomics", "https://www.10xgenomics.com/careers", "Biotech"),
    ("Varo Bank", "https://www.varobank.com/careers", "FinTech"),
    ("DeepScribe", "https://www.deepscribe.ai/careers", "Health AI"),
    ("Datassential", "https://datassential.com/careers", "Data"),
    ("Precision Neuroscience", "https://precisionneuroscience.com/careers", "MedTech"),
    ("Praxent", "https://praxent.com/careers", "Software"),
    ("Sanctuary AI", "https://www.sanctuaryai.com/careers", "Robotics"),
    ("SaaS Labs", "https://www.saaslabs.co/careers", "SaaS"),
    ("Uniqode", "https://uniqode.com/careers", "SaaS"),
    ("Digantara", "https://digantara.com/careers", "SpaceTech"),
    ("GreyLabs AI", "https://greylabs.ai/careers", "AI"),
    ("Flexiple", "https://flexiple.com/careers", "Hiring"),
    ("Health Note", "https://healthnote.com/careers", "Healthcare"),
]


def seed_user_companies():
    inserted = 0
    with get_conn() as conn:
        for name, career_url, domain in USER_PROVIDED_COMPANIES:
            try:
                conn.execute(
                    """
                    INSERT INTO companies_custom (name, domain, career_url, status)
                    VALUES (?, ?, ?, 'active')
                    ON CONFLICT(domain) DO UPDATE SET
                        career_url=excluded.career_url,
                        status='active'
                    """,
                    (name, domain, career_url)
                )
                inserted += 1
            except Exception as e:
                logger.debug(f"DB error for {name}: {e}")
        conn.commit()

    logger.info(f"[seed_user_custom_companies] Successfully seeded {inserted} custom company career URLs!")
    print(f"Successfully ingested {inserted} custom company career URLs into database!")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    seed_user_companies()
