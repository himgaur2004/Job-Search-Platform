import requests
import json

url = "https://raw.githubusercontent.com/outscal/OpenJobs/main/data/companies_v2.json"
resp = requests.get(url)
if resp.ok:
    data = resp.json()
    print(f"Total companies: {len(data)}")
    print("Sample:")
    print(json.dumps(data[:3], indent=2))
else:
    print(f"Failed: {resp.status_code}")
