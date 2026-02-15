import requests
import firebase_admin
from firebase_admin import credentials, firestore, messaging
from datetime import datetime
import pytz
import json

# ==============================
# 🔐 Initialize Firebase
# ==============================

cred = credentials.Certificate("serviceAccountKey.json")
firebase_admin.initialize_app(cred)

db = firestore.client()

# ==============================
# 🌏 Timezone (IST)
# ==============================

ist = pytz.timezone("Asia/Kolkata")
now = datetime.now(ist)

# ==============================
# 🔎 Fetch ONLY 1 Latest Job
# ==============================

BASE_URL = "https://jobcode.in/wp-json/wp/v2/posts"

print("Fetching latest job from API...")

response = requests.get(
    BASE_URL,
    params={
        "per_page": 1,
        "page": 1
    },
    timeout=30
)

if response.status_code != 200:
    print("❌ Failed to fetch jobs")
    exit()

data = response.json()

if not data:
    print("❌ No jobs found")
    exit()

job = data[0]

slug = job.get("slug")
title = job.get("title", {}).get("rendered", "")
description = job.get("excerpt", {}).get("rendered", "")
content = job.get("content", {}).get("rendered", "")

apply_link = f"https://jobcode.in/{slug}/"

# ==============================
# 📦 Prepare Firestore Data
# ==============================

job_data = {
    "active": True,
    "applyLink": apply_link,
    "approved": True,
    "company": "",
    "contactEmail": "",
    "createdAt": now,
    "description": description,
    "experience": "",
    "jobType": "Full-time",
    "jobid": "",
    "jobposterid": "",
    "location": "",
    "postedAt": now,
    "preferredSkills": "",
    "requirements": content,
    "salary": "",
    "skill": "",
    "source": "Jobcode",
    "sourceFile": "",
    "title": title
}

print("\n==============================")
print("🔥 JOB TO BE INSERTED:")
print("==============================")
print(json.dumps({k: str(v) for k, v in job_data.items()}, indent=2))

# ==============================
# 🔍 Check If Already Exists
# ==============================

doc_ref = db.collection("Directjobs").document(slug)

if doc_ref.get().exists:
    print("\n⚠ Job already exists in Firestore. Skipping insert.")
else:
    doc_ref.set(job_data)
    print("\n✅ Job inserted into Directjobs collection.")

    # ==============================
    # 🔔 Send Notification For THIS JOB
    # ==============================

    message = messaging.Message(
        notification=messaging.Notification(
            title="🚀 New Job Posted",
            body=title,
        ),
        topic="all_users",
    )

    response = messaging.send(message)
    print("\n📢 Notification sent successfully:", response)

print("\n✅ Test script completed.")
