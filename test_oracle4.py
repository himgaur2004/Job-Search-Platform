import requests
import json
from services.ats_aggregator import _HEADERS

domain = "jpmc.fa.oraclecloud.com"
site = "CX_1001"
# Adding ?q=Keyword='Software'
url = f"https://{domain}/hcmRestApi/resources/latest/recruitingCEJobRequisitions?onlyData=true&expand=requisitionList&finder=findReqs;siteNumber={site},limit=25&q=Keyword='Software'"
resp = requests.get(url, headers=_HEADERS)
print(resp.status_code)
data = resp.json()
reqs = data.get("items", [])
if reqs and "requisitionList" in reqs[0]:
    for j in reqs[0]["requisitionList"][:5]:
        print(f"Title: {j.get('Title')} | Loc: {j.get('PrimaryLocation')}")
else:
    print("No jobs found matching Software")
