import requests
import json
from services.ats_aggregator import _HEADERS

domain = "jpmc.fa.oraclecloud.com"
site = "CX_1001"
url = f"https://{domain}/hcmRestApi/resources/latest/recruitingCEJobRequisitions?onlyData=true&expand=requisitionList&finder=findReqs;siteNumber={site},limit=500"
resp = requests.get(url, headers=_HEADERS)
print(resp.status_code)
data = resp.json()
reqs = data.get("items", [])
count = 0
if reqs and "requisitionList" in reqs[0]:
    jobs = reqs[0]["requisitionList"]
    print(f"Total jobs fetched: {len(jobs)}")
    for j in jobs:
        if "Software" in j.get("Title", ""):
            print(f"Title: {j.get('Title')} | Loc: {j.get('PrimaryLocation')}")
            count += 1
print(f"Software jobs: {count}")
