import requests
import json
import csv
import re
from io import StringIO
import os

# Target file
TARGET_JSON = "india_tech_companies.json"

ats_map = {
    "greenhouse": r"boards\.greenhouse\.io/([^/]+)",
    "lever": r"jobs\.lever\.co/([^/]+)",
    "workday": r"([^/]+)\.myworkdayjobs\.com",
    "workable": r"apply\.workable\.com/([^/]+)"
}

companies = []
seen = set()

def add_company(name, ats, token):
    if not name or not ats or not token:
        return
    token = token.split("?")[0].strip()
    # Normalize tokens
    if token in ["", "embed", "jobs", "careers"]:
        return
    key = f"{ats}:{token}"
    if key not in seen:
        seen.add(key)
        companies.append({
            "name": name.strip(),
            "ats": ats.strip(),
            "token": token
        })

def load_openjobs():
    print("Loading OpenJobs dataset...")
    url = "https://raw.githubusercontent.com/outscal/OpenJobs/main/data/companies_v2.json"
    try:
        resp = requests.get(url, timeout=10)
        data = resp.json()
        for c in data:
            name = c.get("name")
            for link in c.get("ats_links", []):
                for ats_name, pattern in ats_map.items():
                    match = re.search(pattern, link)
                    if match:
                        add_company(name, ats_name, match.group(1))
                        break
    except Exception as e:
        print(f"Error loading OpenJobs: {e}")

def load_state_of_ats():
    print("Loading state-of-ats-2026 dataset...")
    url = "https://raw.githubusercontent.com/Kayvan-Zahiri/state-of-ats-2026/main/data/companies.csv"
    try:
        resp = requests.get(url, timeout=10)
        csv_file = StringIO(resp.text)
        # Skip commented lines at the top
        for _ in range(5):
            next(csv_file)
        reader = csv.DictReader(csv_file)
        for row in reader:
            name = row.get("name")
            ats_system = row.get("ats_system", "").lower()
            slug = row.get("slug")
            
            # Map ats_system to our types
            ats = None
            if "greenhouse" in ats_system: ats = "greenhouse"
            elif "lever" in ats_system: ats = "lever"
            elif "workday" in ats_system: ats = "workday"
            elif "workable" in ats_system: ats = "workable"
            
            if ats and slug:
                add_company(name, ats, slug)
    except Exception as e:
        print(f"Error loading state-of-ats: {e}")

def load_existing():
    print("Loading existing india_tech_companies.json...")
    try:
        with open(TARGET_JSON, "r") as f:
            data = json.load(f)
            for c in data:
                ats = c.get("ats")
                name = c.get("name")
                if ats == "oracle":
                    # Oracle requires domain and site
                    key = f"oracle:{c.get('domain')}"
                    if key not in seen:
                        seen.add(key)
                        companies.append(c)
                else:
                    add_company(name, ats, c.get("token"))
    except Exception as e:
        print(f"Error loading existing: {e}")

if __name__ == "__main__":
    load_existing()
    load_state_of_ats()
    load_openjobs()
    
    # We want top 2000 companies. Since our lists are high quality tech, 
    # we just take the first 2000.
    final_list = companies[:2000]
    
    print(f"Collected {len(companies)} total ATS companies.")
    print(f"Saving {len(final_list)} to {TARGET_JSON}...")
    
    with open(TARGET_JSON, "w") as f:
        json.dump(final_list, f, indent=4)
        
    print("Done!")
