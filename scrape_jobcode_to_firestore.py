import requests
import firebase_admin
from firebase_admin import credentials, firestore, messaging
from datetime import datetime
import pytz
import json
from bs4 import BeautifulSoup

# =====================================
# 🔐 Initialize Firebase
# =====================================

cred = credentials.Certificate("serviceAccountKey.json")
firebase_admin.initialize_app(cred)

db = firestore.client()

# =====================================
# 🌏 Timezone (IST)
# =====================================

ist = pytz.timezone("Asia/Kolkata")
now = datetime.now(ist)

# =====================================
# 🔎 Fetch ONLY 1 Latest Job
# =====================================

API_URL = "https://jobcode.in/wp-json/wp/v2/posts"

print("Fetching latest job from Jobcode API...")

response = requests.get(
    API_URL,
    params={
        "per_page": 1,
        "page": 1
    },
    timeout=30
)

if response.status_code != 200:
    print("❌ Failed to fetch jobs:", response.status_code)
    exit()

data = response.json()

if not data:
    print("❌ No jobs found")
    exit()

job = data[0]

slug = job.get("slug", "")
title = job.get("title", {}).get("rendered", "")
content = job.get("content", {}).get("rendered", "")
description = job.get("excerpt", {}).get("rendered", "")

# =====================================
# 🔗 Extract REAL Apply Link
# =====================================

soup = BeautifulSoup(content, "html.parser")

apply_link = ""

for a in soup.find_all("a", href=True):
    if "apply" in a.get_text(strip=True).lower():
        apply_link = a["href"]
        break

if not apply_link:
    apply_link = f"https://jobcode.in/{slug}/"

# =====================================
# 📦 Prepare Firestore Data
# =====================================

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
print("🔥 JOB DETAILS TO BE ADDED:")
print("==============================")
print(json.dumps({k: str(v) for k, v in job_data.items()}, indent=2))

# =====================================
# 🔍 Check If Already Exists
# =====================================

doc_ref = db.collection("Directjobs").document(slug)

if doc_ref.get().exists:
    print("\n⚠ Job already exists in Firestore. Skipping insert.")
else:
    doc_ref.set(job_data)
    print("\n✅ Job inserted into Directjobs collection.")

    # =====================================
    # 🔔 Send FCM Notification
    # =====================================

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
