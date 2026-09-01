import requests
import json
from services.ats_aggregator import _HEADERS

subdomain = "mastercard"
url = f"https://{subdomain}.myworkdayjobs.com/wday/cxs/{subdomain}/CorporateCareers/jobs"
payload = {
    "appliedFacets": {},
    "limit": 20,
    "offset": 0,
    "searchText": "Software Engineer",
}
resp = requests.post(url, json=payload, headers={**_HEADERS, "Content-Type": "application/json"})
print(f"Status: {resp.status_code}")
try:
    print(json.dumps(resp.json(), indent=2)[:500])
except Exception as e:
    print(resp.text[:500])
