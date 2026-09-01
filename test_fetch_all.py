from services.ats_aggregator import fetch_all_ats
import time

start = time.time()
jobs = fetch_all_ats("Software", "Remote")
duration = time.time() - start
print(f"Fetched {len(jobs)} jobs in {duration:.2f} seconds.")
