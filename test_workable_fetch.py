import json
from services.ats_aggregator import fetch_workable

with open("india_tech_companies.json") as f:
    comps = json.load(f)

comp = [c for c in comps if c.get("ats") == "workable"][0]
print(f"Testing {comp['name']}")
jobs = fetch_workable(comp, "Engineer", "India")
print(f"Found {len(jobs)}")
