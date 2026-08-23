"""Iteration 31 helper: create/delete ephemeral advertiser + referral-partner accounts and clear login_failures.

Usage: python iter31_ephemeral.py create|cleanup
"""
import os
import sys

import requests
from dotenv import dotenv_values
from pymongo import MongoClient

BASE = (dotenv_values("/app/frontend/.env").get("REACT_APP_BACKEND_URL") or "").rstrip("/")
be = dotenv_values("/app/backend/.env")
client = MongoClient(os.environ.get("MONGO_URL") or be.get("MONGO_URL"))
db = client[os.environ.get("DB_NAME") or be.get("DB_NAME")]

ACCOUNTS = [
    ("test_iter31_adv@example.com", "PROPERTY_ADVERTISER", "OWNER"),
    ("test_iter31_ref@example.com", "REFERRAL_PARTNER", None),
]
PASSWORD = "Passw0rd!23"


def cleanup():
    for email, _, _ in ACCOUNTS:
        user = db.users.find_one({"email": email})
        if user:
            db.advertiser_profiles.delete_many({"user_id": user["id"]})
            db.referral_partner_profiles.delete_many({"user_id": user["id"]})
            db.users.delete_one({"id": user["id"]})
            print("deleted", email)
    db.login_failures.delete_many({})
    print("login_failures cleared:", db.login_failures.count_documents({}))


def create():
    cleanup()
    for email, category, rel in ACCOUNTS:
        payload = {"name": "TEST Iter31", "email": email, "phone": "+67570000001",
                   "password": PASSWORD, "account_category": category}
        if rel:
            payload["advertiser_relationship_type"] = rel
        r = requests.post(f"{BASE}/api/auth/register", json=payload, timeout=30)
        print(email, r.status_code, r.text[:150])


if __name__ == "__main__":
    {"create": create, "cleanup": cleanup}[sys.argv[1]]()
