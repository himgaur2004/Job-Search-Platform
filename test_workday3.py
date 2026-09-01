import json
from services.ats_aggregator import fetch_workday

with open("india_tech_companies.json") as f:
    comps = json.load(f)

for comp in [c for c in comps if c.get("ats") == "workday"][:3]:
    print(f"Testing {comp['name']}")
    jobs = fetch_workday(comp, "Software Engineer", "India")
    print(f"Found {len(jobs)} jobs")
