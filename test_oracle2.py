import requests
import json
from services.ats_aggregator import _HEADERS

domain = "jpmc.fa.oraclecloud.com"
site = "CX_1001"
url = f"https://{domain}/hcmRestApi/resources/latest/recruitingCEJobRequisitions?onlyData=true&expand=requisitionList&finder=findReqs;siteNumber={site},limit=25"
resp = requests.get(url, headers=_HEADERS)
print(resp.status_code)
try:
    data = resp.json()
    items = data.get("items", [])
    if items:
        reqs = items[0].get("requisitionList", [])
        print(f"Reqs found: {len(reqs)}")
    else:
        print("No items found")
except Exception as e:
    print(e)
    print(resp.text[:500])
