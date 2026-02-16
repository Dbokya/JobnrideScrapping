import os
import requests
import json

# Create an email campaign via Brevo REST API (/v3/emailCampaigns)
# Usage:
#   set BREVO_API_V3_KEY to xkeysib-... key
#   set RECIPIENT_LIST_IDS to comma-separated list IDs in Brevo (eg: 2,7)
#   python create_brevo_campaign.py

API_KEY = os.getenv("BREVO_API_V3_KEY")
SENDER_NAME = os.getenv("BREVO_SENDER_NAME", "JobNRide")
SENDER_EMAIL = os.getenv("BREVO_SENDER_EMAIL", "support@jobnride.com")
LIST_IDS = os.getenv("RECIPIENT_LIST_IDS")

if not API_KEY:
    print("ERROR: set BREVO_API_V3_KEY environment variable to your xkeysib key")
    raise SystemExit(1)

if not LIST_IDS:
    print("ERROR: set RECIPIENT_LIST_IDS environment variable to comma-separated Brevo list IDs")
    raise SystemExit(1)

list_ids = [int(x.strip()) for x in LIST_IDS.split(",") if x.strip()]

url = "https://api.brevo.com/v3/emailCampaigns"
headers = {
    "api-key": API_KEY,
    "Content-Type": "application/json",
}

payload = {
    "name": "JobNRide Campaign via API",
    "subject": "JobNRide - Latest Opportunities for You",
    "sender": {"name": SENDER_NAME, "email": SENDER_EMAIL},
    "type": "classic",
    "htmlContent": "<p>Congratulations! You successfully sent this example campaign via the Brevo API.</p>",
    "recipients": {"listIds": list_ids},
    # optional: schedule_at in format "YYYY-MM-DD HH:mm:ss"
}

resp = requests.post(url, headers=headers, json=payload, timeout=30)
print(resp.status_code)
try:
    print(json.dumps(resp.json(), indent=2))
except Exception:
    print(resp.text)

if resp.status_code >= 400:
    print("Failed to create campaign. Check API key, sender verification, and list IDs.")
else:
    print("Campaign created successfully.")
