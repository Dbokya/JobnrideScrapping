import os
import hashlib
import firebase_admin
from firebase_admin import credentials, firestore, messaging
from datetime import datetime
import pytz

IST = pytz.timezone("Asia/Kolkata")

_db = None

def init_firebase():
    global _db
    if not firebase_admin._apps:
        cred = credentials.Certificate("serviceaccount/jobnride-97d77-firebase-adminsdk-fbsvc-20ce6e6129.json")
        firebase_admin.initialize_app(cred)
    _db = firestore.client()
    return _db

def get_db():
    global _db
    if _db is None:
        init_firebase()
    return _db

def make_job_hash(company: str, title: str, location: str) -> str:
    raw = f"{company.lower().strip()}|{title.lower().strip()}|{location.lower().strip()}"
    return hashlib.md5(raw.encode()).hexdigest()

def is_duplicate(company: str, title: str, location: str, apply_link: str) -> bool:
    db = get_db()
    # Check by applyLink first (fastest)
    if apply_link:
        existing = list(db.collection("Directjobs").where("applyLink", "==", apply_link).limit(1).stream())
        if existing:
            return True
    # Check by dedup hash
    job_hash = make_job_hash(company, title, location)
    existing = list(db.collection("Directjobs").where("dedupHash", "==", job_hash).limit(1).stream())
    return len(existing) > 0

def get_highest_api_id() -> int:
    db = get_db()
    try:
        jobs = db.collection("Directjobs").where("jobid", ">=", "apijob").where("jobid", "<", "apijok").stream()
        max_id = 0
        for job in jobs:
            jobid = job.to_dict().get("jobid", "")
            if jobid.startswith("apijob"):
                try:
                    num = int(jobid.replace("apijob", ""))
                    if num > max_id:
                        max_id = num
                except ValueError:
                    continue
        return max_id
    except Exception as e:
        print(f"⚠ Error getting highest API job ID: {e}")
        return 0

def save_job(job_data: dict, job_counter: int) -> bool:
    db = get_db()
    company = job_data.get("company", "")
    title = job_data.get("title", "")
    location = job_data.get("location", "")
    apply_link = job_data.get("applyLink", "")

    if is_duplicate(company, title, location, apply_link):
        print(f"⏭️  Duplicate: {title[:60]} @ {company}")
        return False

    now = datetime.now(IST)
    unique_jobid = f"apijob{job_counter:04d}"
    job_hash = make_job_hash(company, title, location)

    record = {
        "active": True,
        "approved": True,
        "title": title,
        "company": company,
        "location": location,
        "experience": job_data.get("experience", "Not Specified"),
        "jobType": job_data.get("jobType", "Full-Time"),
        "salary": job_data.get("salary", "Not Disclosed"),
        "description": job_data.get("description", ""),
        "requirements": job_data.get("requirements", "Not Specified"),
        "preferredSkills": job_data.get("preferredSkills", "Not Specified"),
        "skill": job_data.get("preferredSkills", "Not Specified"),
        "responsibilities": job_data.get("responsibilities", "Not Specified"),
        "applyLink": apply_link,
        "featuredImage": job_data.get("featuredImage", ""),
        "jobid": unique_jobid,
        "jobposterid": "",
        "source": job_data.get("source", "api"),
        "sourceFile": "unified_scraper",
        "jobFor": job_data.get("jobFor", "experienced"),
        "dedupHash": job_hash,
        "country": job_data.get("country", ""),
        "category": job_data.get("category", ""),
        "createdAt": now,
        "postedAt": now,
    }

    db.collection("Directjobs").add(record)
    print(f"✅ Saved [{unique_jobid}]: {title[:55]} @ {company}")
    return True

def send_notification(title: str, body: str):
    db = get_db()
    tokens = []
    users = db.collection("users").stream()
    for user in users:
        token_docs = db.collection("users").document(user.id).collection("deviceTokens").stream()
        for token_doc in token_docs:
            token = token_doc.to_dict().get("token")
            if token:
                tokens.append(token)

    if not tokens:
        print("⚠ No device tokens found.")
        return

    # FCM allows max 500 tokens per multicast
    chunk_size = 500
    success_total = 0
    fail_total = 0
    for i in range(0, len(tokens), chunk_size):
        chunk = tokens[i:i + chunk_size]
        message = messaging.MulticastMessage(
            notification=messaging.Notification(title=title, body=body),
            android=messaging.AndroidConfig(
                priority="high",
                notification=messaging.AndroidNotification(
                    sound="default",
                    channel_id="job_alerts",
                    priority="high",
                ),
            ),
            apns=messaging.APNSConfig(
                payload=messaging.APNSPayload(
                    aps=messaging.Aps(sound="default", badge=1, content_available=True)
                )
            ),
            tokens=chunk,
        )
        response = messaging.send_each_for_multicast(message)
        success_total += response.success_count
        fail_total += response.failure_count

    print(f"✓ Notifications sent — Success: {success_total}, Failed: {fail_total}")
