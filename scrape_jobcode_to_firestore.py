import requests
from bs4 import BeautifulSoup
import firebase_admin
from firebase_admin import credentials, firestore, messaging
from datetime import datetime
import pytz
import re
import json
import os

# ---------------- INITIALIZE FIREBASE ---------------- #

if not firebase_admin._apps:
    cred = credentials.Certificate("serviceAccountKey.json")
    firebase_admin.initialize_app(cred)

db = firestore.client()

# ---------------- CONFIG ---------------- #

API_URL = "https://jobcode.in/wp-json/wp/v2/posts?per_page=100&page="

# ---------------- JOB CLASSIFICATION ---------------- #

def classify_job(job):
    title = (job.get("title", "") or "").lower()
    experience = (job.get("experience", "") or "").lower()

    combined = f"{title} {experience}"

    # Strict intern match
    if re.search(r'\bintern(ship)?\b', combined):
        return "intern"

    # Fresher detection
    if re.search(r'\b(fresher|entry level|junior)\b', combined):
        return "fresher"

    # Experience range like 0-2
    match = re.search(r'(\d+)\s*[-–]\s*(\d+)', experience)
    if match:
        start = int(match.group(1))
        if start <= 1:
            return "fresher"

    return "experienced"

# ---------------- FETCH JOBS ---------------- #

def fetch_jobs():
    page = 1
    all_jobs = []

    while True:
        print(f"Fetching page {page}...")
        response = requests.get(API_URL + str(page))

        if response.status_code != 200:
            break

        data = response.json()
        if not data:
            break

        for post in data:
            job = parse_job(post)
            if job:
                all_jobs.append(job)

        page += 1

    print(f"Total jobs fetched: {len(all_jobs)}")
    return all_jobs

# ---------------- PARSE SINGLE JOB ---------------- #

def parse_job(post):
    title = post.get("title", {}).get("rendered", "")
    link = post.get("link", "")
    content = post.get("content", {}).get("rendered", "")

    soup = BeautifulSoup(content, "html.parser")

    # Extract Apply Link
    apply_link = ""
    apply_button = soup.find("a", string=re.compile("Apply", re.IGNORECASE))
    if apply_button and apply_button.get("href"):
        apply_link = apply_button.get("href")

    # Remove scripts and styles
    for script in soup(["script", "style"]):
        script.decompose()

    description = str(soup)

    now = datetime.now(pytz.timezone("Asia/Kolkata"))

    job_data = {
        "active": True,
        "approved": True,
        "title": BeautifulSoup(title, "html.parser").get_text(),
        "company": extract_company(description),
        "location": extract_field(description, "Location"),
        "experience": extract_field(description, "Experience"),
        "jobType": extract_field(description, "Job Type"),
        "salary": extract_field(description, "Salary"),
        "description": description,
        "requirements": "",
        "preferredSkills": "",
        "applyLink": apply_link if apply_link else link,
        "jobid": "",
        "jobposterid": "",
        "source": "",
        "sourceFile": "",
        "jobFor": "",
        "createdAt": now,
        "postedAt": now,
    }

    job_data["jobFor"] = classify_job(job_data)

    return job_data

# ---------------- SIMPLE FIELD EXTRACTOR ---------------- #

def extract_field(text, keyword):
    match = re.search(fr"{keyword}[:\-]?\s*(.*)", text, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return ""

def extract_company(text):
    match = re.search(r'About the Company\s*[–\-]\s*(.*?)<', text, re.IGNORECASE)
    if match:
        return BeautifulSoup(match.group(1), "html.parser").get_text()
    return "Unknown"

# ---------------- SEND FCM ---------------- #

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

    response = messaging.send_each_for_multicast(message)

    print(f"Notification success: {response.success_count}")
    print(f"Notification failed: {response.failure_count}")

# ---------------- SAVE JOBS ---------------- #

def save_jobs(jobs):
    for job in jobs:

        # Avoid duplicate by title + company
        existing = (
            db.collection("Directjobs")
            .where(filter=firestore.FieldFilter("title", "==", job["title"]))
            .where(filter=firestore.FieldFilter("company", "==", job["company"]))
            .limit(1)
            .stream()
        )

        if list(existing):
            continue

        print("\nAdding Job:")
        print(json.dumps({k: str(v) for k, v in job.items()}, indent=2))

        db.collection("Directjobs").add(job)

        send_notification(job["title"], job["company"])

        print("Job added successfully.\n")

# ---------------- MAIN ---------------- #

if __name__ == "__main__":
    jobs = fetch_jobs()

    if jobs:
        save_jobs(jobs)

    print("Script completed successfully.")
