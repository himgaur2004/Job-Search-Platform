import json
import sqlite3
import os
import requests
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from services.db import get_conn

def seed_db():
    print("Downloading massive ATS lists...")
    
    urls = {
        "greenhouse": "https://raw.githubusercontent.com/Feashliaa/job-board-aggregator/main/data/greenhouse_companies.json",
        "lever": "https://raw.githubusercontent.com/Feashliaa/job-board-aggregator/main/data/lever_companies.json"
    }
    
    total_added = 0
    with get_conn() as conn:
        for ats_type, url in urls.items():
            print(f"Fetching {ats_type} companies...")
            try:
                resp = requests.get(url, timeout=10)
                resp.raise_for_status()
                # format is usually ["token1", "token2", ...] or {"token": "name"}
                data = resp.json()
                
                # Format normalization
                if isinstance(data, list):
                    companies = []
                    for item in data:
                        if isinstance(item, dict) and 'board_token' in item:
                            companies.append((item.get('name', item['board_token']), item['board_token']))
                        elif isinstance(item, str):
                            companies.append((item, item))
                elif isinstance(data, dict):
                    companies = [(name, token) for token, name in data.items()]
                else:
                    print(f"Unknown data format for {ats_type}")
                    continue
                    
                print(f"Inserting {len(companies)} {ats_type} companies...")
                for name, token in companies:
                    try:
                        conn.execute(
                            "INSERT OR IGNORE INTO ats_companies (name, ats_type, token) VALUES (?, ?, ?)",
                            (name, ats_type, token)
                        )
                        total_added += 1
                    except sqlite3.Error as e:
                        print(f"DB Error on {token}: {e}")
                        
            except Exception as e:
                print(f"Error fetching {url}: {e}")
                
        # Also include local india_tech_companies.json
        local_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "india_tech_companies.json")
        if os.path.exists(local_path):
            print("Loading local india_tech_companies.json...")
            with open(local_path, "r") as f:
                local_data = json.load(f)
                for c in local_data:
                    if 'token' not in c or 'ats' not in c:
                        continue
                    try:
                        conn.execute(
                            "INSERT OR IGNORE INTO ats_companies (name, ats_type, token) VALUES (?, ?, ?)",
                            (c.get("name", c["token"]), c["ats"], c["token"])
                        )
                        total_added += 1
                    except sqlite3.Error:
                        pass
                        
    print(f"Successfully seeded ATS database with {total_added} companies.")

if __name__ == "__main__":
    seed_db()
