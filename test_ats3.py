import os
import json
from services.ats_aggregator import fetch_all_ats

jobs = fetch_all_ats("Software Engineer", "India")
for j in jobs:
    print(f"Title: {j['title']} | Location: {j['location']}")
