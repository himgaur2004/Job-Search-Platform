import socket
import requests
import json
from services.ats_aggregator import _HEADERS

tenant = "mastercard"
clusters = ["wd1", "wd3", "wd5", "myworkdayjobs"]
sites = ["External", "CX_1", "CX_2", "CorporateCareers", "Careers", "mastercard"]

payload = {
    "appliedFacets": {},
    "limit": 20,
    "offset": 0,
    "searchText": "Software",
}

valid_domain = None
for cluster in clusters:
    domain = f"{tenant}.{cluster}.myworkdayjobs.com" if cluster != "myworkdayjobs" else f"{tenant}.myworkdayjobs.com"
    try:
        socket.gethostbyname(domain)
        valid_domain = domain
        break
    except socket.gaierror:
        pass

if valid_domain:
    print(f"Found valid domain: {valid_domain}")
    for site in sites:
        url = f"https://{valid_domain}/wday/cxs/{tenant}/{site}/jobs"
        r = requests.post(url, json=payload, headers={**_HEADERS, "Content-Type": "application/json", "Accept": "application/json"}, timeout=3)
        if r.status_code == 200:
            print(f"SUCCESS with site {site} -> Found {len(r.json().get('jobPostings', []))} jobs")
            break
        else:
            print(f"Site {site} returned {r.status_code}")
