import logging
from services.ats_aggregator import fetch_all_ats

logging.basicConfig(level=logging.DEBUG)
jobs = fetch_all_ats("Software", "India")
print(f"Total: {len(jobs)}")
