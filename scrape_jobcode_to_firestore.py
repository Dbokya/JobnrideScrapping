import requests
import re
import pytz
import json
from datetime import datetime
from bs4 import BeautifulSoup
import firebase_admin
from firebase_admin import credentials, firestore, messaging
from google import genai
import os

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

# ------------------ FETCH ALL JOBS ------------------
def fetch_all_jobs():
    jobs = []
    page = 1
    while True:
        print(f"Fetching page {page}...")
        response = requests.get(BASE_API + str(page))
        if response.status_code != 200:
            break
        data = response.json()
        if not data:
            break
        jobs.extend(data)
        page += 1
    print(f"Total jobs fetched: {len(jobs)}")
    return jobs

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
Analyze the following job posting and extract information in a strict JSON format. 
Return ONLY a valid JSON object with these exact fields (no markdown, no code blocks, just JSON):

Job Title: {title}

Job Content:
{clean_text}

Extract the following fields:
- company: Company/organization name (string, if not found use "Not Specified")
- location: Job location/city/country (string, if not found use "Not Specified")
- experience: Years of experience required (string like "2-5 years" or "Fresher" or "0-2 years", if not found use "Not Specified")
- jobType: Type of employment (string: "Full-time", "Part-time", "Contract", "Internship", "Freelance", if not found use "Not Specified")
- salary: Salary/compensation mentioned (string, if not found use "Not Disclosed")
- description: Brief job description/summary in 2-3 sentences (string, clean and concise)
- requirements: Key requirements/qualifications as comma-separated string (string, if not found use "Not Specified")
- preferredSkills: Required/preferred skills as comma-separated string (string, if not found use "Not Specified")
- notificationTitle: A short, clean, VARIED notification title (max 6-7 words). Use different formats each time like:
  * "[Role] Opening at [Company]" 
  * "[Company] Hiring [Role]"
  * "[Role] Position at [Company]"
  * "Join [Company] as [Role]"
  * "[Company] seeks [Role]"
  Make it engaging and varied, not repetitive. (string)

Return ONLY the JSON object, nothing else.
"""

    try:
        response = client.models.generate_content(model=MODEL_ID, contents=prompt)
        response_text = response.text.strip()
        if response_text.startswith("```"):
            response_text = re.sub(r'^```json?\n', '', response_text)
            response_text = re.sub(r'\n```$', '', response_text)
        job_details = json.loads(response_text)
    except Exception:
        job_details = {
            "company": "Not Specified",
            "location": "Not Specified",
            "experience": "Not Specified",
            "jobType": "Not Specified",
            "salary": "Not Disclosed",
            "description": clean_text[:500],
            "requirements": "Not Specified",
            "preferredSkills": "Not Specified",
            "notificationTitle": f"New Job at Company"
        }

    apply_link = extract_apply_link(content_html)
    if not apply_link:
        apply_link = default_link
    job_details["applyLink"] = apply_link

    return job_details

# ------------------ SEND NOTIFICATION ------------------
def send_notification(notification_title):
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

    print(f"Total tokens found: {len(tokens)}")
    BATCH_SIZE = 500
    success_total = 0
    failure_total = 0

    for i in range(0, len(tokens), BATCH_SIZE):
        batch = tokens[i:i + BATCH_SIZE]
        message = messaging.MulticastMessage(
            notification=messaging.Notification(
                title="🚀 New Job Alert!",
                body=notification_title,
            ),
            android=messaging.AndroidConfig(
                priority='high',
                notification=messaging.AndroidNotification(
                    sound='default',
                    channel_id='job_alerts',
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
            tokens=batch,
        )
        response = messaging.send_each_for_multicast(message)
        success_total += response.success_count
        failure_total += response.failure_count

    print(f"Notification sending completed. Success: {success_total}, Failed: {failure_total}")

# ------------------ SAVE JOBS ------------------
def save_jobs(jobs):
    first_run = True
    existing_docs = list(db.collection("Directjobs").limit(1).stream())
    if existing_docs:
        first_run = False

    newly_added_jobs = []

    for job in jobs:
        title = job.get("title", {}).get("rendered", "")
        content = job.get("content", {}).get("rendered", "")
        link = job.get("link", "")

        clean_title = BeautifulSoup(title, "html.parser").get_text()

        existing = db.collection("Directjobs").where("applyLink", "==", link).limit(1).stream()
        if list(existing):
            continue

        ai_extracted = extract_job_details_with_ai(clean_title, content, link)
        now = datetime.now(IST)
        job_data = {
            "active": True,
            "approved": True,
            "title": clean_title,
            "company": ai_extracted.get("company", "Not Specified"),
            "location": ai_extracted.get("location", "Not Specified"),
            "experience": ai_extracted.get("experience", "Not Specified"),
            "jobType": ai_extracted.get("jobType", "Not Specified"),
            "salary": ai_extracted.get("salary", "Not Disclosed"),
            "description": ai_extracted.get("description", ""),
            "requirements": ai_extracted.get("requirements", "Not Specified"),
            "preferredSkills": ai_extracted.get("preferredSkills", "Not Specified"),
            "applyLink": ai_extracted.get("applyLink", link),
            "jobid": "",
            "jobposterid": "",
            "source": "jobcode.in",
            "sourceFile": "scrape_jobcode_to_firestore.py",
            "jobFor": classify_job(clean_title, content),
            "createdAt": now,
            "postedAt": now,
        }

        db.collection("Directjobs").add(job_data)
        newly_added_jobs.append(job_data)

    # Send notification for only the first newly added job (most recent)
    if newly_added_jobs and not first_run:
        latest_job = newly_added_jobs[-1]  # last added job
        notification_title = latest_job.get("notificationTitle", f"New Job at {latest_job['company']}")
        send_notification(notification_title)

    print(f"Summary: {len(newly_added_jobs)} new jobs added")
    if first_run:
        print("First run completed. No notifications sent.")
    elif len(newly_added_jobs) == 0:
        print("No new jobs found. No notifications sent.")

# ------------------ MAIN ------------------
if __name__ == "__main__":
    jobs = fetch_all_jobs()
    save_jobs(jobs)
