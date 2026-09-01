import requests
import json
from services.ats_aggregator import _HEADERS

token = "infoedge"
url = f"https://apply.workable.com/api/v3/accounts/{token}/jobs"
resp = requests.post(
    url,
    json={"query": "Engineer", "location": [], "remote": True},
    timeout=10,
    headers=_HEADERS,
)
print(resp.status_code)
try:
    print(json.dumps(resp.json(), indent=2)[:500])
except Exception as e:
    print(resp.text[:500])
