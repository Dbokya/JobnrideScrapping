import os
import smtplib
import ssl
import pandas as pd
from email.message import EmailMessage
from datetime import datetime
import firebase_admin
from firebase_admin import credentials, firestore

# ---------------- FIREBASE INIT ----------------

cred = credentials.Certificate("serviceAccountKey.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

# ---------------- CONFIG ----------------

SMTP_HOST = "smtp.hostinger.com"
SMTP_PORT = 465
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")

if not SMTP_USER or not SMTP_PASS:
    raise ValueError("SMTP credentials not set")

EXCEL_FILE = "users.xlsx"

# ---------------- SEND EMAIL ----------------

def send_email(to_email, name):
    msg = EmailMessage()
    msg["From"] = SMTP_USER
    msg["To"] = to_email
    msg["Subject"] = "🚀 Join JobnRide Today"

    msg.set_content(f"""
Hi {name},

We noticed you haven’t created your JobnRide account yet.

Start earning referral rewards and ride earnings today.

Download and register now.

Team JobnRide
""")

    context = ssl.create_default_context()

    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=context) as server:
        server.login(SMTP_USER, SMTP_PASS)
        server.send_message(msg)

# ---------------- CHECK ACCOUNT ----------------

def check_account_exists(email):
    users = db.collection("users").where("email", "==", email).limit(1).stream()
    return any(users)

# ---------------- MAIN ----------------

def run():
    df = pd.read_excel(EXCEL_FILE)

    for index, row in df.iterrows():
        email = row["email"]
        name = row["name"]

        account_exists = check_account_exists(email)

        if account_exists:
            df.at[index, "accountCreated"] = "Yes"
            continue

        if row.get("accountCreated") != "Yes":
            send_email(email, name)
            df.at[index, "lastEmailSent"] = datetime.utcnow()

    df.to_excel(EXCEL_FILE, index=False)
    print("Automation completed")

if __name__ == "__main__":
    run()
