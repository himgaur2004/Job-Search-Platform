import json
from services.ats_aggregator import fetch_oracle

with open("india_tech_companies.json") as f:
    comps = json.load(f)

comp = [c for c in comps if c.get("ats") == "oracle"][0]
print(f"Testing {comp['name']}")
jobs = fetch_oracle(comp, "Software Engineer", "India")
print(f"Jobs: {len(jobs)}")
