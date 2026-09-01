import os
import json
from services.ats_aggregator import fetch_all_ats

jobs = fetch_all_ats("Software Engineer", "Remote")
print(f"Total jobs: {len(jobs)}")
