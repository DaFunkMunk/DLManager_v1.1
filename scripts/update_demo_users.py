"""Update demo users in MongoDB Atlas with richer attributes."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from pymongo import MongoClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DOTENV_PATH = PROJECT_ROOT / ".env"

if DOTENV_PATH.exists():
    load_dotenv(DOTENV_PATH)

uri = os.getenv("DEMO_MONGO_URI")
db_name = os.getenv("DEMO_MONGO_DB", "dl_demo")

if not uri:
    raise SystemExit("DEMO_MONGO_URI is not defined; update .env before running.")

client = MongoClient(uri)
db = client[db_name]
users = db["users"]

USER_UPDATES = {
    "u_alex": {
        "location": "Midland Field Office",
        "role": "Production Engineer",
        "employmentType": "Full-time",
        "tags": ["Operations", "Responder"],
        "directoryGroups": ["g_drill_permian"],
        "manager": "Erika Howard",
        "tenureDays": 820,
        "orgUnit": "Operations/Permian",
    },
    "u_casey": {
        "location": "Houston HQ",
        "role": "IT Systems Lead",
        "employmentType": "Full-time",
        "tags": ["Corporate", "Leadership", "IT"],
        "directoryGroups": ["g_corp_it"],
        "manager": "Casey Lee",
        "tenureDays": 1500,
        "orgUnit": "Corporate/IT",
    },
    "u_devon": {
        "location": "Midland Field Office",
        "role": "Field Specialist",
        "employmentType": "Full-time",
        "tags": ["Operations"],
        "directoryGroups": ["g_drill_permian"],
        "manager": "Alex Rivera",
        "tenureDays": 420,
        "orgUnit": "Operations/Permian",
    },
    "u_erika": {
        "location": "South Ops HQ",
        "role": "Operations Manager",
        "employmentType": "Full-time",
        "tags": ["Leadership", "Operations"],
        "directoryGroups": ["g_drill_permian"],
        "manager": "Maria Gonzales",
        "tenureDays": 1120,
        "orgUnit": "Operations/South",
    },
    "u_frank": {
        "location": "Houston Data Center",
        "role": "Data Scientist",
        "employmentType": "Full-time",
        "tags": ["Analytics", "IT"],
        "directoryGroups": ["g_corp_it"],
        "manager": "Casey Lee",
        "tenureDays": 680,
        "orgUnit": "Corporate/Analytics",
    },
    "u_jane": {
        "location": "EVIN Operations Center",
        "role": "Network Engineer",
        "employmentType": "Full-time",
        "tags": ["EVIN", "Responder"],
        "directoryGroups": ["g_acl_evin_north"],
        "manager": "Casey Lee",
        "tenureDays": 980,
        "orgUnit": "Corporate/Network",
    },
    "u_maria": {
        "location": "Houston HQ",
        "role": "HSE Director",
        "employmentType": "Full-time",
        "tags": ["HSE", "Leadership"],
        "directoryGroups": ["g_hse_incident_response"],
        "manager": "Executive Leadership",
        "tenureDays": 1825,
        "orgUnit": "Corporate/HSE",
    },
    "u_temp": {
        "location": "East Projects Office",
        "role": "Project Engineer",
        "employmentType": "Contractor",
        "tags": ["Contractor", "East"],
        "directoryGroups": ["g_msg_prod_east"],
        "manager": "Erika Howard",
        "tenureDays": 120,
        "orgUnit": "Operations/East",
    },
}

for user_id, fields in USER_UPDATES.items():
    result = users.update_one({"_id": user_id}, {"$set": fields})
    if result.matched_count == 0:
        print(f"[WARN] No user document with _id={user_id} was found.")
    else:
        print(f"[OK] Updated {user_id}.")

print("Done.")
