from services.ats_aggregator import fetch_all_ats
import time

start = time.time()
jobs = fetch_all_ats("Software", "Remote")
print(f"Total jobs: {len(jobs)} in {time.time()-start:.2f}s")
