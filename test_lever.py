from services.ats_aggregator import fetch_lever
import json

with open("india_tech_companies.json") as f:
    comps = json.load(f)

lever_comps = [c for c in comps if c.get("ats") == "lever"]
if lever_comps:
    c = lever_comps[0]
    print(c)
    print(fetch_lever(c, "Software", "India"))
