import requests
import firebase_admin
from firebase_admin import credentials, firestore, messaging
from datetime import datetime
import pytz
import re
import os
import json

# ===============================
# 🔥 FIREBASE INITIALIZATION
# ===============================

if not firebase_admin._apps:
    cred = credentials.Certificate("serviceAccountKey.json")
    firebase_admin.initialize_app(cred)

db = firestore.client()

# ===============================
# 🔥 CONFIG
# ===============================

API_BASE_URL = "https://jobcode.in/wp-json/wp/v2/posts?per_page=100&page="
IST = pytz.timezone("Asia/Kolkata")


# ===============================
# 🔥 JOB CLASSIFIER
# ===============================

def classify_job(job):
    title = (job.get("title", "") or "").lower()
    description = (job.get("description", "") or "").lower()
    experience = (job.get("experience", "") or "").lower()

    combined = f"{title} {description} {experience}"

    if "intern" in combined:
        return "intern"

    if (
        "fresher" in combined
        or "0-1" in combined
        or "0-2" in combined
        or "entry level" in combined
        or "junior" in combined
    ):
        return "fresher"

    # Try numeric detection
    match = re.search(r'(\d+)\s*[-–]\s*(\d+)', experience)
    if match:
        start = int(match.group(1))
        if start <= 1:
            return "fresher"

    return "experienced"


# ===============================
# 🔥 FETCH JOBS FROM API
# ===============================

def fetch_jobs():
    all_jobs = []
    page = 1

    while True:
        print(f"Fetching page {page}...")
        response = requests.get(API_BASE_URL + str(page))

        if response.status_code != 200:
            break

        jobs = response.json()

        if not jobs:
            break

        all_jobs.extend(jobs)
        page += 1

    print(f"Total jobs fetched: {len(all_jobs)}")
    return all_jobs


# ===============================
# 🔥 CHECK DUPLICATE
# ===============================

def job_exists(title, company):
    query = (
        db.collection("Directjobs")
        .where("title", "==", title)
        .where("company", "==", company)
        .limit(1)
        .stream()
    )
    return any(query)


# ===============================
# 🔥 SEND FCM NOTIFICATION
# ===============================

def send_notification(title, company):
    print("Sending notification...")

    tokens = []

    users = db.collection("users").stream()
    for user in users:
        device_tokens = (
            db.collection("users")
            .document(user.id)
            .collection("deviceTokens")
            .stream()
        )

        for token_doc in device_tokens:
            token = token_doc.to_dict().get("token")
            if token:
                tokens.append(token)

    if not tokens:
        print("No tokens found.")
        return

    message = messaging.MulticastMessage(
        notification=messaging.Notification(
            title="🚀 New Job Posted!",
            body=f"{title} at {company}"
        ),
        tokens=tokens,
    )

    response = messaging.send_multicast(message)
    print(f"Notifications sent: {response.success_count}")


# ===============================
# 🔥 SAVE JOBS TO FIRESTORE
# ===============================

def save_jobs(jobs):
    new_jobs_count = 0

    for job in jobs:

        title = job.get("title", {}).get("rendered", "")
        link = job.get("link", "")
        content = job.get("content", {}).get("rendered", "")

        if not title:
            continue

        company = extract_company(content)
        location = extract_location(content)
        experience = extract_experience(content)
        job_type = extract_job_type(content)

        if job_exists(title, company):
            continue

        job_for = classify_job({
            "title": title,
            "description": content,
            "experience": experience
        })

        now = datetime.now(IST)

        job_data = {
            "active": True,
            "approved": True,
            "title": title,
            "company": company,
            "location": location,
            "experience": experience,
            "jobType": job_type,
            "salary": "",
            "description": content,
            "requirements": "",
            "preferredSkills": "",
            "applyLink": link,
            "jobid": "",
            "jobposterid": "",
            "source": "",
            "sourceFile": "",
            "jobFor": job_for,
            "createdAt": now,
            "postedAt": now,
        }

        print("Adding Job:")
        print(json.dumps(job_data, indent=2, default=str))

        db.collection("Directjobs").add(job_data)

        send_notification(title, company)

        new_jobs_count += 1

        # Only add ONE job for testing
        break

    print(f"New jobs added: {new_jobs_count}")


# ===============================
# 🔥 EXTRACTION HELPERS
# ===============================

def extract_company(content):
    match = re.search(r'Company:\s*(.*?)<', content)
    return match.group(1).strip() if match else "Unknown"


def extract_location(content):
    match = re.search(r'Location:\s*(.*?)<', content)
    return match.group(1).strip() if match else ""


def extract_experience(content):
    match = re.search(r'Experience:\s*(.*?)<', content)
    return match.group(1).strip() if match else ""


def extract_job_type(content):
    match = re.search(r'Job Type:\s*(.*?)<', content)
    return match.group(1).strip() if match else ""


# ===============================
# 🔥 MAIN
# ===============================

if __name__ == "__main__":
    jobs = fetch_jobs()
    save_jobs(jobs)
