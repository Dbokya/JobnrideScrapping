import requests
import re
import pytz
import json
from datetime import datetime
from bs4 import BeautifulSoup
import firebase_admin
from firebase_admin import credentials, firestore, messaging
import google.generativeai as genai
import os

# ------------------ FIREBASE INIT ------------------

cred = credentials.Certificate("serviceAccountKey.json")
firebase_admin.initialize_app(cred)

db = firestore.client()

# ------------------ AI INIT ------------------

# Configure Gemini AI from environment variable (GitHub Secret)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY environment variable is not set. Please configure it in GitHub Secrets.")

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

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
    """
    Uses Gemini AI to extract structured job information from the job posting.
    """
    # Clean HTML content
    soup = BeautifulSoup(content_html, "html.parser")
    clean_text = soup.get_text(separator="\n").strip()
    
    # Create a comprehensive prompt for the AI
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
        response = model.generate_content(prompt)
        response_text = response.text.strip()
        
        # Remove markdown code blocks if present
        if response_text.startswith("```"):
            response_text = re.sub(r'^```json?\n', '', response_text)
            response_text = re.sub(r'\n```$', '', response_text)
            response_text = response_text.strip()
        
        # Parse the JSON response
        job_details = json.loads(response_text)
        
        # Ensure all required fields exist with defaults
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
        
        # Merge with defaults
        for key, default_value in defaults.items():
            if key not in job_details or not job_details[key] or job_details[key].strip() == "":
                job_details[key] = default_value
        
        # Extract or verify apply link
        apply_link = extract_apply_link(content_html)
        if not apply_link:
            apply_link = default_link
        
        job_details["applyLink"] = apply_link
        
        print(f"✓ AI extracted: {job_details.get('company', 'Unknown')} - {job_details.get('location', 'Unknown')}")
        
        return job_details
        
    except json.JSONDecodeError as e:
        print(f"⚠ JSON parsing error: {e}")
        print(f"Response was: {response_text[:200]}")
        return get_default_job_details(title, clean_text, default_link)
    except Exception as e:
        print(f"⚠ AI extraction error: {e}")
        return get_default_job_details(title, clean_text, default_link)


def get_default_job_details(title, clean_text, link):
    """
    Fallback function when AI extraction fails.
    """
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
        "applyLink": link
    }


# ------------------ SEND NOTIFICATION ------------------

def send_notification(notification_title):
    print("Sending notification...")

    tokens = []

    users = db.collection("users").stream()

    for user in users:
        token_docs = (
            db.collection("users")
            .document(user.id)
            .collection("deviceTokens")
            .stream()
        )

        for token_doc in token_docs:
            token = token_doc.to_dict().get("token")
            if token:
                tokens.append(token)

    if not tokens:
        print("No device tokens found.")
        return

    # Create notification with sound for both Android and iOS
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
        tokens=tokens,
    )

    response = messaging.send_each_for_multicast(message)

    print("✓ Notification sent with sound")
    print("  Success:", response.success_count)
    print("  Failed:", response.failure_count)


# ------------------ SAVE JOBS ------------------

def save_jobs(jobs):
    first_run = True
    new_jobs_added = 0

    # If collection empty → first run
    existing_docs = list(db.collection("Directjobs").limit(1).stream())
    if existing_docs:
        first_run = False

    # TESTING: Process only 1 job
    jobs = jobs[:1]
    print(f"\n⚠ TEST MODE: Processing only 1 job\n")

    for job in jobs:
        title = job.get("title", {}).get("rendered", "")
        content = job.get("content", {}).get("rendered", "")
        link = job.get("link", "")

        # Clean title
        clean_title = BeautifulSoup(title, "html.parser").get_text()

        # Check if already exists using applyLink
        existing = (
            db.collection("Directjobs")
            .where("applyLink", "==", link)
            .limit(1)
            .stream()
        )

        if list(existing):
            continue  # skip existing jobs

        # Extract job details using AI
        print(f"\nProcessing: {clean_title}")
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
        
        notification_title = ai_extracted.get("notificationTitle", f"New Job at {job_data['company']}")

        print(f"✓ Adding Job: {job_data['title']} at {job_data['company']}")

        db.collection("Directjobs").add(job_data)

        new_jobs_added += 1

        # Send notification ONLY if NOT first run
        if not first_run:
            send_notification(notification_title)

    print(f"\n{'='*50}")
    print(f"Summary: {new_jobs_added} new jobs added")
    print(f"{'='*50}")

    if first_run:
        print("First run completed. No notifications sent.")
    elif new_jobs_added == 0:
        print("No new jobs found. No notifications sent.")


# ------------------ MAIN ------------------

if __name__ == "__main__":
    jobs = fetch_all_jobs()
    save_jobs(jobs)
