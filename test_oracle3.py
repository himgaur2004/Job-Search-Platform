import requests
import json
from services.ats_aggregator import _HEADERS

domain = "jpmc.fa.oraclecloud.com"
site = "CX_1001"
url = f"https://{domain}/hcmRestApi/resources/latest/recruitingCEJobRequisitions?onlyData=true&expand=requisitionList&finder=findReqs;siteNumber={site},limit=25"
resp = requests.get(url, headers=_HEADERS)
data = resp.json()
reqs = data.get("items", [])[0].get("requisitionList", [])
for j in reqs[:5]:
    print(f"Title: {j.get('Title')} | Loc: {j.get('PrimaryLocation')}")
