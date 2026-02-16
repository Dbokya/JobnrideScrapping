import pandas as pd
import argparse
import smtplib
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import time
import os
import firebase_admin
from firebase_admin import credentials, firestore

# Firebase Setup (optional) - only initialize if service account file exists
SERVICE_ACCOUNT_REL = os.path.join("..", "serviceaccount", "jobnride-97d77-firebase-adminsdk-fbsvc-20ce6e6129.json")
SERVICE_ACCOUNT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), SERVICE_ACCOUNT_REL))
db = None
if os.path.exists(SERVICE_ACCOUNT_PATH):
    try:
        cred = credentials.Certificate(SERVICE_ACCOUNT_PATH)
        if not firebase_admin._apps:
            firebase_admin.initialize_app(cred)
        db = firestore.client()
    except Exception as e:
        print(f"⚠️ Firebase initialization failed: {e}")
        db = None
else:
    print(f"⚠️ Firebase service account not found at {SERVICE_ACCOUNT_PATH}; skipping Firebase checks.")

# Email Provider Configuration
BREVO_API_V3_KEY = os.getenv("BREVO_API_V3_KEY", "")

EMAIL_PROVIDERS = {
    "hostinger": {
        "smtp_server": "smtp.hostinger.com",
        "smtp_port": 465,
        "sender_email": "support@jobnride.com",
        "sender_password": os.getenv("HOSTINGER_PASSWORD", "Jobnride@27061994"),
        "daily_limit": 100,
        "name": "Hostinger"
    },
    "brevo": {
        "smtp_server": "smtp-relay.brevo.com",
        "smtp_port": 587,  # Brevo uses STARTTLS on port 587
        "sender_email": os.getenv("BREVO_SENDER_EMAIL", "support@jobnride.com"),
        "sender_password": os.getenv("BREVO_API_KEY", ""),  # Set this before using Brevo
        "daily_limit": 100,
        "name": "Brevo (Sendinblue)"
    }
}

SENDER_NAME = "Durgesh Tiwari - JobNRide"

# Email Template
def get_email_template():
    return """
<html>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
    <p>Hi,</p>
    
    <p>Hope you're doing well.</p>
    
    <p>You recently shared your email on a LinkedIn post related to job opportunities, so I'm reaching out to you directly.</p>
    
    <p>We've built <strong>JobNRide</strong> to help job seekers get:</p>
    <ul>
        <li>Latest job alerts</li>
        <li>Direct connections with company employees for referrals</li>
        <li>Instant updates on off-campus drives</li>
        <li>Opportunities from MNCs and startups in one place</li>
    </ul>
    
    <p>If you'd like to explore these opportunities, you can check out the JobNRide app here:</p>
    
    <p>To receive instant and relevant job updates, we recommend that you <strong>download the JobNRide app</strong> and complete your full profile. This helps us match you with the right opportunities faster.</p>
    
    <div style="margin: 20px 0;">
        <p><strong>For Android Users</strong><br>
        <a href="https://play.google.com/store/apps/details?id=com.kdads.jobnride" style="color: #4CAF50; text-decoration: none;">📱 Download on Play Store</a></p>
        
        <p><strong>For iOS Users</strong><br>
        <a href="https://apps.apple.com/in/app/jobnride/id6753137262" style="color: #4CAF50; text-decoration: none;">📱 Download on App Store</a></p>
    </div>
    
    <p>Feel free to reply to this email if you have any questions or if you're looking for jobs in a specific domain—I'll be happy to help.</p>
    
    <hr style="border: none; border-top: 1px solid #ddd; margin: 30px 0;">
    
    <div style="font-size: 0.9em; color: #666;">
        <p><strong>JobNRide</strong><br>
        Smart Rides. Smarter Careers.</p>
        
        <p><strong>Durgesh Tiwari</strong><br>
        ✉️ <a href="mailto:support@jobnride.com">support@jobnride.com</a><br>
        🌐 <a href="https://jobnride.com">Download JobNRide</a></p>
        
        <p style="font-size: 0.8em; color: #999;">© 2025 KDAds Solutions Private Limited. All rights reserved.</p>
    </div>
</body>
</html>
"""

def send_email(to_email, provider_config, use_starttls=False):
    """Send email to a single recipient using specified provider"""
    # If this is Brevo and we have an API v3 key, prefer REST API
    if provider_config.get('name', '').lower().startswith('brevo') and BREVO_API_V3_KEY:
        return send_via_brevo_api(to_email)
    try:
        # Create message
        msg = MIMEMultipart('alternative')
        msg['From'] = f"{SENDER_NAME} <{provider_config['sender_email']}>"
        msg['To'] = to_email
        msg['Subject'] = "Exclusive Job Opportunities with JobNRide - Your Career Partner"
        
        # Attach HTML content
        html_content = get_email_template()
        msg.attach(MIMEText(html_content, 'html'))
        
        # Send email - different methods for SSL vs STARTTLS
        if use_starttls:
            # Brevo uses STARTTLS
            with smtplib.SMTP(provider_config['smtp_server'], provider_config['smtp_port']) as server:
                server.starttls()
                server.login(provider_config['sender_email'], provider_config['sender_password'])
                server.send_message(msg)
        else:
            # Hostinger uses SSL
            with smtplib.SMTP_SSL(provider_config['smtp_server'], provider_config['smtp_port']) as server:
                server.login(provider_config['sender_email'], provider_config['sender_password'])
                server.send_message(msg)
        
        print(f"✓ Sent to: {to_email}")
        return True
        
    except Exception as e:
        print(f"✗ Failed to send to {to_email}: {e}")
        return False

def send_via_brevo_api(to_email):
    """Send a single transactional email via Brevo REST API (/v3/smtp/email)"""
    api_key = BREVO_API_V3_KEY
    if not api_key:
        print("✗ Brevo API key not configured (BREVO_API_V3_KEY)")
        return False

    url = "https://api.brevo.com/v3/smtp/email"
    headers = {"api-key": api_key, "Content-Type": "application/json"}
    payload = {
        "sender": {"name": SENDER_NAME, "email": EMAIL_PROVIDERS['brevo']['sender_email']},
        "to": [{"email": to_email}],
        "subject": "Exclusive Job Opportunities with JobNRide - Your Career Partner",
        "htmlContent": get_email_template(),
    }
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=30)
        if resp.status_code >= 400:
            print(f"✗ Brevo API failed ({resp.status_code}): {resp.text}")
            return False
        print(f"✓ Sent via Brevo API to: {to_email}")
        return True
    except Exception as e:
        print(f"✗ Brevo API error: {e}")
        return False

def check_user_exists_in_firebase(email):
    """Check if user with this email exists in Firebase"""
    try:
        if not db:
            # Firebase unavailable locally — assume user does not exist
            return False
        users = list(db.collection("users").where("email", "==", email).limit(1).stream())
        return len(users) > 0
    except Exception as e:
        print(f"⚠ Error checking Firebase for {email}: {e}")
        return False

def categorize_users():
    """Categorize users into existing accounts and new users"""
    print("\n" + "="*70)
    print("🔍 CATEGORIZING USERS - CHECKING FIREBASE ACCOUNTS")
    print("="*70 + "\n")
    
    # Load users data
    try:
        df = pd.read_csv('users.xlsx')
    except:
        print("❌ ERROR: Could not read users.xlsx file")
        return None, None
    
    existing_users = []
    new_users = []
    
    print(f"Checking {len(df)} users against Firebase...")
    
    for idx, row in df.iterrows():
        email = row['email']
        
        if pd.isna(email) or email.strip() == "":
            continue
        
        # Check if user exists in Firebase
        if check_user_exists_in_firebase(email):
            existing_users.append(row)
            print(f"✓ Found in Firebase: {email}")
        else:
            new_users.append(row)
            print(f"○ New user: {email}")
        
        time.sleep(0.1)  # Small delay to avoid overwhelming Firebase
    
    # Create DataFrames
    df_existing = pd.DataFrame(existing_users) if existing_users else pd.DataFrame(columns=df.columns)
    df_new = pd.DataFrame(new_users) if new_users else pd.DataFrame(columns=df.columns)
    
    # Save categorized files
    df_existing.to_csv('users_with_accounts.xlsx', index=False)
    df_new.to_csv('users_to_email.xlsx', index=False)
    
    print("\n" + "="*70)
    print("📊 CATEGORIZATION COMPLETE")
    print("="*70)
    print(f"✓ Users with accounts: {len(existing_users)} (saved to users_with_accounts.xlsx)")
    print(f"○ New users to email: {len(new_users)} (saved to users_to_email.xlsx)")
    print("="*70 + "\n")
    
    return df_existing, df_new

def main():
    parser = argparse.ArgumentParser(description='Send emails via Hostinger or Brevo')
    parser.add_argument('--test-email', help='Send a single test email to this address and exit')
    parser.add_argument('--provider', choices=['hostinger', 'brevo', 'auto'], default='auto', help='Provider to use for test-email (default: auto)')
    args = parser.parse_args()

    # If test-email provided, perform a one-off send and exit
    if args.test_email:
        to_addr = args.test_email
        # Provider selection for test mode
        prov = args.provider
        if prov == 'auto':
            # prefer Brevo API if available, else Hostinger
            if BREVO_API_V3_KEY:
                provider_key = 'brevo'
            else:
                provider_key = 'hostinger'
        else:
            provider_key = prov

        provider = EMAIL_PROVIDERS[provider_key]
        use_starttls = True if provider_key == 'brevo' else False
        print(f"Test mode: sending single email to {to_addr} via {provider['name']}")
        ok = send_email(to_addr, provider, use_starttls)
        print("Done. Success:" , ok)
        return
    # Choose email provider
    print("\n" + "="*70)
    print("📧 EMAIL PROVIDER SELECTION")
    print("="*70)
    print("1. Hostinger (100 emails/day)")
    print("2. Brevo (100 emails/day)")
    print("="*70)
    
    provider_choice = input("Select provider (1 or 2): ").strip()
    
    if provider_choice == "1":
        provider_key = "hostinger"
        use_starttls = False
    elif provider_choice == "2":
        provider_key = "brevo"
        use_starttls = True
        if not EMAIL_PROVIDERS["brevo"]["sender_password"]:
            print("❌ ERROR: BREVO_API_KEY environment variable not set")
            print("Set it using: $env:BREVO_API_KEY='your-brevo-api-key'")
            return
    else:
        print("❌ Invalid choice")
        return
    
    provider = EMAIL_PROVIDERS[provider_key]
    
    print(f"\n✓ Using {provider['name']} ({provider['sender_email']})")
    
    # First, categorize users
    df_existing, df_new = categorize_users()
    
    if df_new is None:
        return
    
    if len(df_new) == 0:
        print("✅ No new users to email - all users already have accounts!")
        return
    
    # Filter users who haven't received emails yet
    users_to_email = df_new[df_new['lastEmailSent'].isna() | (df_new['lastEmailSent'] == '')]
    
    total_users = len(users_to_email)
    emails_to_send = min(total_users, provider['daily_limit'])
    
    print("\n" + "="*70)
    print(f"📧 JOBNRIDE - USER EMAIL CAMPAIGN ({provider['name']})")
    print("="*70)
    print(f"Total new users: {len(df_new)}")
    print(f"Users pending emails: {total_users}")
    print(f"Emails to send today: {emails_to_send} (Limit: {provider['daily_limit']})")
    print("="*70 + "\n")
    
    if emails_to_send == 0:
        print("✅ All users have already received emails!")
        return
    
    # Confirm before sending
    confirm = input(f"Send {emails_to_send} emails via {provider['name']}? (yes/no): ").lower()
    if confirm != 'yes':
        print("❌ Email sending cancelled")
        return
    
    # Send emails
    sent_count = 0
    failed_count = 0
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    for idx, row in users_to_email.head(emails_to_send).iterrows():
        email = row['email']
        
        if pd.isna(email) or email.strip() == "":
            print(f"⏭️  Skipped row {idx}: No email address")
            continue
        
        # Send email
        if send_email(email, provider, use_starttls):
            # Update lastEmailSent in dataframe
            df_new.at[idx, 'lastEmailSent'] = current_time
            sent_count += 1
        else:
            failed_count += 1
        
        # Small delay to avoid rate limiting
        time.sleep(1)
    
    # Save updated data
    df_new.to_csv('users_to_email.xlsx', index=False)
    
    # Summary
    print("\n" + "="*70)
    print(f"📊 CAMPAIGN SUMMARY ({provider['name']})")
    print("="*70)
    print(f"✓ Successfully sent: {sent_count}")
    print(f"✗ Failed: {failed_count}")
    print(f"📝 Updated users_to_email.xlsx with timestamps")
    print("="*70 + "\n")
    
    remaining = len(df_new[df_new['lastEmailSent'].isna() | (df_new['lastEmailSent'] == '')])
    if remaining > 0:
        print(f"ℹ️  {remaining} users remaining for next batch")
        if provider_key == "hostinger" and remaining > 0:
            print(f"💡 TIP: Use Brevo for the next {min(remaining, 100)} emails tomorrow!")
    else:
        print("🎉 All users have been contacted!")

if __name__ == "__main__":
    main()
