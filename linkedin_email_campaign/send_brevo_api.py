import os
import requests
import json

# Sends a single transactional email via Brevo REST API (/v3/smtp/email)
# Usage:
#   set env BREVO_API_V3_KEY to your xkeysib-... key
#   python send_brevo_api.py recipient@example.com

API_KEY = os.getenv("BREVO_API_V3_KEY")
SENDER_NAME = os.getenv("BREVO_SENDER_NAME", "JobNRide")
SENDER_EMAIL = os.getenv("BREVO_SENDER_EMAIL", "support@jobnride.com")

if not API_KEY:
    print("ERROR: set BREVO_API_V3_KEY environment variable to your xkeysib key")
    raise SystemExit(1)

import sys
if len(sys.argv) < 2:
    print("Usage: python send_brevo_api.py recipient@example.com")
    raise SystemExit(1)

recipient = sys.argv[1]

url = "https://api.brevo.com/v3/smtp/email"
headers = {
    "api-key": API_KEY,
    "Content-Type": "application/json",
}

payload = {
    "sender": {"name": SENDER_NAME, "email": SENDER_EMAIL},
    "to": [{"email": recipient}],
    "subject": "Test email from JobNRide via Brevo API",
    "htmlContent": "<p>Hello, this is a test email sent via Brevo REST API.</p>",
}

resp = requests.post(url, headers=headers, json=payload, timeout=30)
print(resp.status_code)
try:
    print(json.dumps(resp.json(), indent=2))
except Exception:
    print(resp.text)

if resp.status_code >= 400:
    print("Failed to send via Brevo API. Check API key and sender verification.")
else:
    print("Sent via Brevo API successfully.")
