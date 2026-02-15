import requests
import re
import pytz
import json
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import firebase_admin
from firebase_admin import credentials, firestore, messaging
import os
import time
import openai

# ------------------ FIREBASE INIT ------------------
cred = credentials.Certificate("serviceAccountKey.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

# ------------------ OPENAI INIT ------------------
OPENAI_API_KEY = os.getenv("OPEN_AI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("OPEN_AI_API_KEY not set in environment variables.")
openai.api_key = OPENAI_API_KEY

# ------------------ CONFIG ------------------
BASE_API = "https://jobcode.in/wp-json/wp/v2/posts?per_page=100&page="
IST = pytz.timezone("Asia/Kolkata")

# ------------------ HELPER FUNCTIONS ------------------

def fetch_jobs_page(page):
    response = requests.get(BASE_API + str(page))
    if response.status_code != 200:
        return []
    return response.json()

def classify_job(title, content):
    text = f"{title} {content}".lower()
    if re.search(r"\bintern(ship)?\b", text):
        return "intern"
    if re.search(r"\b(fresher|entry level|junior)\b", text):
        return "fresher"
    return "experienced"

def extract_apply_link(html):
    soup = BeautifulSoup(html, "html.parser")
    apply_button = soup.find("a", string=re.compile("Apply", re.IGNORECASE))
    if apply_button and apply_button.get("href"):
        return apply_button["href"]
    return ""

def extract_job_details_with_ai(title, content_html, default_link):
    soup = BeautifulSoup(content_html, "html.parser")
    clean_text = soup.get_text(separator="\n").strip()
    clean_text_short = clean_text[:1500]  # Limit to save tokens

    prompt = f"""
Extract the job details into strict JSON only, no explanation. 
Use these fields: company, location, experience, jobType, salary, description, requirements, preferredSkills, notificationTitle.

Job Title: {title}
Job Content: {clean_text_short}
"""

    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )
        response_text = response.choices[0].message.content.strip()
        if response_text.startswith("```"):
            response_text = re.sub(r'^```json?\n', '', response_text)
            response_text = re.sub(r'\n```$', '', response_text)

        job_details = json.loads(response_text)

        defaults = {
            "company": "Not Specified",
            "location": "Not Specified",
            "experience": "Not Specified",
            "jobType": "Not Specified",
            "salary": "Not Disclosed",
            "description": clean_text[:300],
            "requirements": "Not Specified",
            "preferredSkills": "Not Specified",
            "notificationTitle": f"New Job at {job_details.get('company','Company')}"
        }

        for key, value in defaults.items():
            if key not in job_details or not job_details[key] or str(job_details[key]).strip() == "":
                job_details[key] = value

        job_details["applyLink"] = extract_apply_link(content_html) or default_link
        return job_details

    except Exception as e:
        print(f"⚠ AI extraction failed: {e}")
        return {
            "company": "Not Specified",
            "location": "Not Specified",
            "experience": "Not Specified",
            "jobType": "Not Specified",
            "salary": "Not Disclosed",
            "description": clean_text[:300],
            "requirements": "Not Specified",
            "preferredSkills": "Not Specified",
            "notificationTitle": f"New Job Available",
            "applyLink": default_link
        }

def save_job(job):
    title_html = job.get("title", {}).get("rendered", "")
    content_html = job.get("content", {}).get("rendered", "")
    link = job.get("link", "")

    clean_title = BeautifulSoup(title_html, "html.parser").get_text()

    # Skip if job already exists
    existing = list(db.collection("Directjobs").where("applyLink", "==", link).limit(1).stream())
    if existing:
        return False

    ai_data = extract_job_details_with_ai(clean_title, content_html, link)
    now = datetime.now(IST)

    job_data = {
        "active": True,
        "approved": True,
        "title": clean_title,
        "company": ai_data.get("company"),
        "location": ai_data.get("location"),
        "experience": ai_data.get("experience"),
        "jobType": ai_data.get("jobType"),
        "salary": ai_data.get("salary"),
        "description": ai_data.get("description"),
        "requirements": ai_data.get("requirements"),
        "preferredSkills": ai_data.get("preferredSkills"),
        "applyLink": ai_data.get("applyLink"),
        "jobid": "",
        "jobposterid": "",
        "source": "jobcode.in",
        "sourceFile": "scrape_jobcode_to_firestore.py",
        "jobFor": classify_job(clean_title, content_html),
        "createdAt": now,
        "postedAt": now,
    }

    db.collection("Directjobs").add(job_data)
    print(f"✓ Added Job: {clean_title}")
    return ai_data.get("notificationTitle")

def send_notification(title):
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

# ------------------ MAIN ------------------
if __name__ == "__main__":
    page = 1
    latest_notification_title = None

    today = datetime.now(IST).date()
    yesterday = today - timedelta(days=1)

    while True:
        jobs = fetch_jobs_page(page)
        if not jobs:
            break

        for job in jobs:
            # Only process jobs posted today or yesterday
            job_date_str = job.get("date")
            if job_date_str:
                job_date = datetime.fromisoformat(job_date_str.replace("Z", "+00:00")).astimezone(IST).date()
                if job_date not in [today, yesterday]:
                    continue

            notification_title = save_job(job)
            if notification_title:
                latest_notification_title = notification_title

            time.sleep(0.5)  # prevent overload

        page += 1

    if latest_notification_title:
        send_notification(latest_notification_title)
        print("Notification sent for the latest added job.")
    else:
        print("No new jobs added. No notifications sent.")
