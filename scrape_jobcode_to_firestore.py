import requests
import re
import pytz
import json
from datetime import datetime
from bs4 import BeautifulSoup
import firebase_admin
from firebase_admin import credentials, firestore, messaging
from google import genai
from google.genai import types
import os
import time

# ------------------ FIREBASE INIT ------------------

cred = credentials.Certificate("serviceAccountKey.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

# ------------------ AI INIT ------------------

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY environment variable is not set. Please configure it in GitHub Secrets.")

client = genai.Client(api_key=GEMINI_API_KEY)
MODEL_ID = "gemini-2.0-flash-exp"

# ------------------ CONFIG ------------------

BASE_API = "https://jobcode.in/wp-json/wp/v2/posts?per_page=100&page="
IST = pytz.timezone("Asia/Kolkata")

# ------------------ FETCH JOBS PAGE BY PAGE ------------------

def fetch_jobs_page(page):
    print(f"Fetching page {page}...")
    response = requests.get(BASE_API + str(page))
    if response.status_code != 200:
        return []
    data = response.json()
    return data

# ------------------ CLASSIFY JOB ------------------

def classify_job(title, content):
    text = f"{title} {content}".lower()
    if re.search(r"\bintern(ship)?\b", text):
        return "intern"
    if re.search(r"\b(fresher|entry level|junior)\b", text):
        return "fresher"
    return "experienced"

# ------------------ EXTRACT APPLY LINK ------------------

def extract_apply_link(html):
    soup = BeautifulSoup(html, "html.parser")
    apply_button = soup.find("a", string=re.compile("Apply", re.IGNORECASE))
    if apply_button and apply_button.get("href"):
        return apply_button["href"]
    return ""

# ------------------ EXTRACT JOB DETAILS WITH AI ------------------

def extract_job_details_with_ai(title, content_html, default_link):
    soup = BeautifulSoup(content_html, "html.parser")
    clean_text = soup.get_text(separator="\n").strip()

    prompt = f"""
Analyze the following job posting and extract information in strict JSON format.
Return ONLY a valid JSON object with these fields:

Job Title: {title}

Job Content:
{clean_text}

Fields:
- company
- location
- experience
- jobType
- salary
- description
- requirements
- preferredSkills
- notificationTitle
Return ONLY JSON object.
"""
    try:
        response = client.models.generate_content(
            model=MODEL_ID,
            contents=prompt
        )
        response_text = response.text.strip()
        if response_text.startswith("```"):
            response_text = re.sub(r'^```json?\n', '', response_text)
            response_text = re.sub(r'\n```$', '', response_text)
            response_text = response_text.strip()
        job_details = json.loads(response_text)

        # Defaults
        defaults = {
            "company": "Not Specified",
            "location": "Not Specified",
            "experience": "Not Specified",
            "jobType": "Not Specified",
            "salary": "Not Disclosed",
            "description": clean_text[:500] if clean_text else "No description available",
            "requirements": "Not Specified",
            "preferredSkills": "Not Specified",
            "notificationTitle": f"New Job at {job_details.get('company', 'Company')}"
        }

        for key, value in defaults.items():
            if key not in job_details or not job_details[key] or job_details[key].strip() == "":
                job_details[key] = value

        apply_link = extract_apply_link(content_html)
        if not apply_link:
            apply_link = default_link
        job_details["applyLink"] = apply_link

        return job_details

    except Exception as e:
        print(f"⚠ AI extraction failed: {e}")
        return {
            "company": "Not Specified",
            "location": "Not Specified",
            "experience": "Not Specified",
            "jobType": "Not Specified",
            "salary": "Not Disclosed",
            "description": clean_text[:500] if clean_text else "No description available",
            "requirements": "Not Specified",
            "preferredSkills": "Not Specified",
            "notificationTitle": f"New Job Available",
            "applyLink": default_link
        }

# ------------------ SEND NOTIFICATION ------------------

def send_notification(title):
    print("Sending notification...")

    tokens = []
    users = db.collection("users").stream()
    for user in users:
        token_docs = db.collection("users").document(user.id).collection("deviceTokens").stream()
        for token_doc in token_docs:
            token = token_doc.to_dict().get("token")
            if token:
                tokens.append(token)

    if not tokens:
        print("No device tokens found.")
        return

    message = messaging.MulticastMessage(
        notification=messaging.Notification(
            title="🚀 New Job Alert!",
            body=title,
        ),
        android=messaging.AndroidConfig(
            priority='high',
            notification=messaging.AndroidNotification(
                sound='default',
                channel_id='job_alerts',
                priority='high',
            )
        ),
        apns=messaging.APNSConfig(
            payload=messaging.APNSPayload(
                aps=messaging.Aps(
                    sound='default',
                    badge=1,
                    content_available=True,
                )
            )
        ),
        tokens=tokens
    )

    response = messaging.send_each_for_multicast(message)
    print("✓ Notification sent")
    print("  Success:", response.success_count)
    print("  Failed:", response.failure_count)

# ------------------ SAVE JOB ------------------

def save_job(job):
    title = job.get("title", {}).get("rendered", "")
    content = job.get("content", {}).get("rendered", "")
    link = job.get("link", "")

    clean_title = BeautifulSoup(title, "html.parser").get_text()

    existing = list(db.collection("Directjobs").where("applyLink", "==", link).limit(1).stream())
    if existing:
        return False  # already exists

    ai_data = extract_job_details_with_ai(clean_title, content, link)
    now = datetime.now(IST)
    job_data = {
        "active": True,
        "approved": True,
        "title": clean_title,
        "company": ai_data.get("company", "Not Specified"),
        "location": ai_data.get("location", "Not Specified"),
        "experience": ai_data.get("experience", "Not Specified"),
        "jobType": ai_data.get("jobType", "Not Specified"),
        "salary": ai_data.get("salary", "Not Disclosed"),
        "description": ai_data.get("description", ""),
        "requirements": ai_data.get("requirements", "Not Specified"),
        "preferredSkills": ai_data.get("preferredSkills", "Not Specified"),
        "applyLink": ai_data.get("applyLink", link),
        "jobid": "",
        "jobposterid": "",
        "source": "jobcode.in",
        "sourceFile": "scrape_jobcode_to_firestore.py",
        "jobFor": classify_job(clean_title, content),
        "createdAt": now,
        "postedAt": now,
    }

    db.collection("Directjobs").add(job_data)
    print(f"✓ Added Job: {clean_title}")
    return ai_data.get("notificationTitle", f"New Job at {job_data['company']}")

# ------------------ MAIN ------------------

if __name__ == "__main__":
    page = 1
    latest_notification_title = None

    while True:
        jobs = fetch_jobs_page(page)
        if not jobs:
            break

        for job in jobs:
            notification_title = save_job(job)
            if notification_title:
                latest_notification_title = notification_title
            time.sleep(1)  # process one job at a time

        page += 1

    if latest_notification_title:
        send_notification(latest_notification_title)
        print("Notification sent for the latest added job.")
    else:
        print("No new jobs added. No notifications sent.")
