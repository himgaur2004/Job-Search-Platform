import json
import requests

with open("india_tech_companies.json") as f:
    comps = json.load(f)
    
wd_comps = [c for c in comps if c.get("ats") == "workday"]
comp = wd_comps[0]
print(f"Testing {comp['name']}")

subdomain = comp.get("subdomain")
site = comp.get("site", "CX_1")
url = f"https://{subdomain}.myworkdayjobs.com/wday/cxs/{subdomain}/{site}/jobs"

payload = {
    "appliedFacets": {},
    "limit": 20,
    "offset": 0,
    "searchText": "Software Engineer",
}

print(f"URL: {url}")
resp = requests.post(url, json=payload, headers={
    "User-Agent": "Mozilla/5.0",
    "Content-Type": "application/json",
    "Accept": "application/json"
})
print(resp.status_code)
try:
    print(json.dumps(resp.json(), indent=2)[:500])
except Exception as e:
    print(resp.text[:500])
