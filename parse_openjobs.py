import requests
import json
import re

url = "https://raw.githubusercontent.com/outscal/OpenJobs/main/data/companies_v2.json"
resp = requests.get(url)
data = resp.json()

ats_map = {
    "greenhouse": r"boards\.greenhouse\.io/([^/]+)",
    "lever": r"jobs\.lever\.co/([^/]+)",
    "workday": r"([^/]+)\.myworkdayjobs\.com",
    "workable": r"apply\.workable\.com/([^/]+)"
}

companies = []
for c in data:
    name = c.get("name")
    for link in c.get("ats_links", []):
        for ats_name, pattern in ats_map.items():
            match = re.search(pattern, link)
            if match:
                token = match.group(1).split("?")[0].strip()
                if token and token not in ["", "embed"]:
                    companies.append({
                        "name": name,
                        "ats": ats_name,
                        "token": token
                    })
                    break

print(f"Total ATS companies found: {len(companies)}")
print(f"Greenhouse: {len([c for c in companies if c['ats'] == 'greenhouse'])}")
print(f"Lever: {len([c for c in companies if c['ats'] == 'lever'])}")
print(f"Workday: {len([c for c in companies if c['ats'] == 'workday'])}")
print(f"Workable: {len([c for c in companies if c['ats'] == 'workable'])}")

# Deduplicate
unique = []
seen = set()
for c in companies:
    key = f"{c['ats']}:{c['token']}"
    if key not in seen:
        seen.add(key)
        unique.append(c)

print(f"Unique ATS companies found: {len(unique)}")
