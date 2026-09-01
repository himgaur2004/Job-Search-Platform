import requests
import json
from services.ats_aggregator import _HEADERS

tenant = "mastercard"
clusters = ["wd1", "wd3", "wd5"]
sites = ["External", "CX_1", "CX_2", "CorporateCareers", "Careers"]

payload = {
    "appliedFacets": {},
    "limit": 20,
    "offset": 0,
    "searchText": "Software Engineer",
}

for cluster in clusters:
    domain = f"{tenant}.{cluster}.myworkdayjobs.com"
    print(f"Trying domain {domain}")
    try:
        # Check if domain resolves/responds
        resp = requests.head(f"https://{domain}", timeout=3)
        if resp.status_code == 200 or resp.status_code == 301 or resp.status_code == 302:
            print(f"Domain {domain} is ALIVE!")
            for site in sites:
                url = f"https://{domain}/wday/cxs/{tenant}/{site}/jobs"
                r2 = requests.post(url, json=payload, headers={**_HEADERS, "Content-Type": "application/json", "Accept": "application/json"}, timeout=3)
                if r2.status_code == 200:
                    print(f"SUCCESS: {url} works! Found {len(r2.json().get('jobPostings', []))} jobs")
                    break
    except Exception as e:
        print(f"Failed {domain}: {e}")
