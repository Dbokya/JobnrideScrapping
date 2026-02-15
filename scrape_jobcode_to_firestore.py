import requests
import firebase_admin
from firebase_admin import credentials, firestore, messaging
from datetime import datetime
import uuid

# ========== FIREBASE INIT ==========
cred = credentials.Certificate("serviceAccountKey.json")
firebase_admin.initialize_app(cred)

db = firestore.client()

API_URL = "https://your-api-endpoint.com"
DIRECT_COLLECTION = "Directjobs"

# ========== FETCH LATEST JOB ==========
def fetch_latest_job():
    print("Fetching latest job...")
    response = requests.get(API_URL)
    data = response.json()

    if not data:
        print("No jobs found")
        return None

    return data[0]

# ========== CLEAN JOB ==========
def normalize_job(job):
    cleaned = {
        "jobId": str(uuid.uuid4()),
        "title": job.get("title", "").strip(),
        "company": job.get("company", "").strip(),
        "location": job.get("location", "").strip(),
        "description": job.get("description", "").strip(),
        "applyLink": job.get("applyLink", ""),
        "createdAt": datetime.utcnow(),
        "source": "direct"
    }

    print("\nFields being added:")
    for k, v in cleaned.items():
        print(f"{k}: {v}")

    return cleaned

# ========== SAVE JOB ==========
def save_job(job_data):
    db.collection(DIRECT_COLLECTION).document(job_data["jobId"]).set(job_data)
    print("✅ Job saved in Directjobs")

# ========== GET ALL TOKENS ==========
def get_all_tokens():
    print("\nFetching device tokens...")
    tokens = []
    android_count = 0
    ios_count = 0

    users = db.collection("users").stream()

    for user in users:
        token_docs = db.collection("users") \
            .document(user.id) \
            .collection("deviceTokens") \
            .stream()

        for token_doc in token_docs:
            token_data = token_doc.to_dict()

            token = token_data.get("token")
            platform = token_data.get("platform")

            if token:
                tokens.append(token)

                if platform == "android":
                    android_count += 1
                elif platform == "ios":
                    ios_count += 1

    print(f"Total Tokens: {len(tokens)}")
    print(f"Android: {android_count}")
    print(f"iOS: {ios_count}")

    return tokens

# ========== SEND NOTIFICATION ==========
def send_notification(tokens, job):
    if not tokens:
        print("No tokens found.")
        return

    print("\nSending notification...")

    message = messaging.MulticastMessage(
        tokens=tokens,
        notification=messaging.Notification(
            title="🚀 New Job Posted!",
            body=f"{job['title']} at {job['company']}"
        ),
        data={
            "type": "job",
            "jobId": job["jobId"],
            "click_action": "FLUTTER_NOTIFICATION_CLICK"
        },
        android=messaging.AndroidConfig(
            priority="high",
        ),
        apns=messaging.APNSConfig(
            headers={
                "apns-priority": "10"
            }
        )
    )

    response = messaging.send_multicast(message)

    print("Success:", response.success_count)
    print("Failure:", response.failure_count)

    # Remove invalid tokens automatically
    if response.failure_count > 0:
        print("Cleaning invalid tokens...")

        for idx, resp in enumerate(response.responses):
            if not resp.success:
                invalid_token = tokens[idx]
                remove_invalid_token(invalid_token)

# ========== REMOVE INVALID TOKEN ==========
def remove_invalid_token(bad_token):
    users = db.collection("users").stream()

    for user in users:
        token_docs = db.collection("users") \
            .document(user.id) \
            .collection("deviceTokens") \
            .where("token", "==", bad_token) \
            .stream()

        for doc in token_docs:
            doc.reference.delete()
            print(f"Removed invalid token: {bad_token}")

# ========== MAIN ==========
def main():
    job = fetch_latest_job()
    if not job:
        return

    cleaned_job = normalize_job(job)
    save_job(cleaned_job)

    tokens = get_all_tokens()
    send_notification(tokens, cleaned_job)

    print("\n🎉 Script Finished Successfully")

if __name__ == "__main__":
    main()
