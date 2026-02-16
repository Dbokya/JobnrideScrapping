import pandas as pd
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import time
import os
import firebase_admin
from firebase_admin import credentials, firestore

# Firebase Setup
cred = credentials.Certificate("../serviceaccount/jobnride-97d77-firebase-adminsdk-fbsvc-20ce6e6129.json")
if not firebase_admin._apps:
    firebase_admin.initialize_app(cred)
db = firestore.client()

# Email Configuration (Hostinger SMTP)
SMTP_SERVER = "smtp.hostinger.com"
SMTP_PORT = 465  # SSL port
SENDER_EMAIL = "support@jobnride.com"
SENDER_PASSWORD = os.getenv("EMAIL_PASSWORD", "Jobnride@27061994")  # Use env var or fallback
SENDER_NAME = "Durgesh Tiwari - JobNRide"
DAILY_LIMIT = 100

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

def send_email(to_email):
    """Send email to a single recipient"""
    try:
        # Create message
        msg = MIMEMultipart('alternative')
        msg['From'] = f"{SENDER_NAME} <{SENDER_EMAIL}>"
        msg['To'] = to_email
        msg['Subject'] = "Exclusive Job Opportunities with JobNRide - Your Career Partner"
        
        # Attach HTML content
        html_content = get_email_template()
        msg.attach(MIMEText(html_content, 'html'))
        
        # Send email via Hostinger SMTP
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.send_message(msg)
        
        print(f"✓ Sent to: {to_email}")
        return True
        
    except Exception as e:
        print(f"✗ Failed to send to {to_email}: {e}")
        return False

def check_user_exists_in_firebase(email):
    """Check if user with this email exists in Firebase"""
    try:
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
    # Check for email password
    if not SENDER_PASSWORD:
        print("❌ ERROR: EMAIL_PASSWORD environment variable not set")
        print("Set it using: $env:EMAIL_PASSWORD='your-password'")
        return
    
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
    emails_to_send = min(total_users, DAILY_LIMIT)
    
    print("\n" + "="*70)
    print("📧 JOBNRIDE - USER EMAIL CAMPAIGN")
    print("="*70)
    print(f"Total new users: {len(df_new)}")
    print(f"Users pending emails: {total_users}")
    print(f"Emails to send today: {emails_to_send} (Limit: {DAILY_LIMIT})")
    print("="*70 + "\n")
    
    if emails_to_send == 0:
        print("✅ All users have already received emails!")
        return
    
    # Confirm before sending
    confirm = input(f"Send {emails_to_send} emails? (yes/no): ").lower()
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
        if send_email(email):
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
    print("📊 CAMPAIGN SUMMARY")
    print("="*70)
    print(f"✓ Successfully sent: {sent_count}")
    print(f"✗ Failed: {failed_count}")
    print(f"📝 Updated users_to_email.xlsx with timestamps")
    print("="*70 + "\n")
    
    remaining = len(df_new[df_new['lastEmailSent'].isna() | (df_new['lastEmailSent'] == '')])
    if remaining > 0:
        print(f"ℹ️  {remaining} users remaining for next batch")
    else:
        print("🎉 All users have been contacted!")

if __name__ == "__main__":
    main()
