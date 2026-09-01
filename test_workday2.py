import json
import requests
from services.ats_aggregator import _HEADERS

with open("india_tech_companies.json") as f:
    comps = json.load(f)

comp = [c for c in comps if c.get("ats") == "workday"][0]
subdomain = comp.get("token", "")
url = f"https://{subdomain}.myworkdayjobs.com/wday/cxs/{subdomain}/External/jobs"
payload = {
    "appliedFacets": {},
    "limit": 20,
    "offset": 0,
    "searchText": "Software Engineer",
}
resp = requests.post(url, json=payload, headers={**_HEADERS, "Content-Type": "application/json"})
print(f"Status: {resp.status_code}")
print(resp.text[:500])
