import os
import hashlib
import firebase_admin
from firebase_admin import credentials, firestore, messaging
from datetime import datetime
import pytz
import re
from normalizer import extract_skills_from_text, parse_posted_date

IST = pytz.timezone("Asia/Kolkata")

_db = None

def _clean_html_in_text(text: str) -> str:
    """Quick HTML tag removal as a safety layer before saving to Firebase."""
    if not text or "<" not in text or ">" not in text:
        return text
    # Remove HTML tags and entities
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&[a-z]+;", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text

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

    # Job's real posting date from the source (None if unknown/unparseable)
    original_posted_at = parse_posted_date(job_data.get("rawPostedDate", ""))

    job_type = job_data.get("jobType", "Full-Time")
    skills_str = _clean_html_in_text(job_data.get("preferredSkills", "Not Specified"))
    
    # Fallback: Extract skills from description if not found or "Not Specified"
    if not skills_str or skills_str == "Not Specified":
        description = job_data.get("description", "")
        if description:
            extracted_skills = extract_skills_from_text(description)
            if extracted_skills and extracted_skills != "Not Specified":
                skills_str = extracted_skills
    
    # Build a keySkills list (array) from comma-separated skills string
    key_skills_list = (
        [s.strip() for s in skills_str.split(",") if s.strip() and s.strip() != "Not Specified"]
        if skills_str and skills_str != "Not Specified" else []
    )

    record = {
        # ── Core identity ──────────────────────────────────────────────────
        "active": True,
        "approved": True,
        "jobid": unique_jobid,
        "jobposterid": "",
        "dedupHash": job_hash,
        "source": job_data.get("source", "api"),
        "sourceFile": "unified_scraper",

        # ── Job basics (Naukri / LinkedIn style) ───────────────────────────
        "title": title,
        "company": company,
        "companyLogo": job_data.get("featuredImage", "") or job_data.get("companyLogo", ""),
        "aboutCompany": _clean_html_in_text(job_data.get("aboutCompany", "")),
        "location": location,
        "country": job_data.get("country", ""),
        "workMode": job_data.get("workMode", "On-site"),       # Remote / Hybrid / On-site
        "jobType": job_type,                                    # Full-Time / Part-Time / Contract / Internship
        "functionalArea": job_data.get("functionalArea", "Information Technology"),
        "industry": job_data.get("industry", "Information Technology"),
        "category": job_data.get("category", ""),

        # ── Requirements ──────────────────────────────────────────────────
        "experience": job_data.get("experience", "Not Specified"),
        "educationRequirement": job_data.get("educationRequirement", "Not Specified"),
        "noticePeriod": job_data.get("noticePeriod", "Not Specified"),
        "totalOpenings": job_data.get("totalOpenings", "Not Specified"),

        # ── Compensation ──────────────────────────────────────────────────
        "salary": job_data.get("salary", "Not Disclosed"),
        "benefits": _clean_html_in_text(job_data.get("benefits", "")),

        # ── Skills ────────────────────────────────────────────────────────
        "preferredSkills": skills_str,
        "skill": skills_str,                                    # legacy alias
        "keySkills": key_skills_list,                           # array for filtering/tags

        # ── Full description sections ──────────────────────────────────────
        "description": _clean_html_in_text(job_data.get("description", "")),
        "responsibilities": _clean_html_in_text(job_data.get("responsibilities", "Not Specified")),
        "requirements": _clean_html_in_text(job_data.get("requirements", "Not Specified")),

        # ── Apply ─────────────────────────────────────────────────────────
        "applyLink": apply_link,

        # ── Notification ──────────────────────────────────────────────────
        "notificationTitle": job_data.get(
            "notificationTitle",
            f"New Job at {company}" if company else "New IT Job Alert"
        ),

        # ── Classification ────────────────────────────────────────────────
        "jobFor": job_data.get("jobFor", "experienced"),

        # ── Timestamps ────────────────────────────────────────────────────
        "createdAt": now,                       # when this scraper saved it
        "postedAt": now,                        # scrape time (legacy field)
        "originalPostedAt": original_posted_at,  # real source posting date (or None)
        "rawPostedDate": job_data.get("rawPostedDate", ""),  # unparsed source value
    }

    db.collection("Directjobs").add(record)
    print(f"✅ Saved [{unique_jobid}]: {title[:55]} @ {company}")
    return unique_jobid

def send_notification(title: str, body: str, data: dict = None):
    """
    Send an FCM push to all registered devices.
    `data` is an optional payload (e.g. deep-link info) delivered to the app on
    tap. FCM requires all data values to be strings, so they're coerced here.
    """
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

    # FCM data payload must be a flat dict of strings
    data_payload = {str(k): str(v) for k, v in (data or {}).items()}

    # FCM allows max 500 tokens per multicast
    chunk_size = 500
    success_total = 0
    fail_total = 0
    for i in range(0, len(tokens), chunk_size):
        chunk = tokens[i:i + chunk_size]
        message = messaging.MulticastMessage(
            notification=messaging.Notification(title=title, body=body),
            data=data_payload,
            android=messaging.AndroidConfig(
                priority="high",
                notification=messaging.AndroidNotification(
                    sound="default",
                    channel_id="job_alerts",
                    priority="high",
                    # Lets the Flutter default FCM service route the tap so the
                    # data payload reaches onMessageOpenedApp for deep-linking.
                    click_action="FLUTTER_NOTIFICATION_CLICK",
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
