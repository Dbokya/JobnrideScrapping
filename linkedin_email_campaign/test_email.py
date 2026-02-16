import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os

# Email Configuration (Hostinger SMTP)
SMTP_SERVER = "smtp.hostinger.com"
SMTP_PORT = 465  # SSL port
SENDER_EMAIL = "support@jobnride.com"
SENDER_PASSWORD = os.getenv("EMAIL_PASSWORD", "Jobnride@27061994")  # Fallback for testing
SENDER_NAME = "Durgesh Tiwari - JobNRide"

# Test recipient
TEST_EMAIL = "Durgeshvtiwari@gmail.com"

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

def send_test_email():
    """Send a test email"""
    
    print("\n" + "="*70)
    print("📧 SENDING TEST EMAIL")
    print("="*70)
    print(f"From: {SENDER_EMAIL}")
    print(f"To: {TEST_EMAIL}")
    print(f"Subject: Exclusive Job Opportunities with JobNRide - Your Career Partner")
    print("="*70 + "\n")
    
    try:
        # Create message
        msg = MIMEMultipart('alternative')
        msg['From'] = f"{SENDER_NAME} <{SENDER_EMAIL}>"
        msg['To'] = TEST_EMAIL
        msg['Subject'] = "Exclusive Job Opportunities with JobNRide - Your Career Partner"
        
        # Attach HTML content
        html_content = get_email_template()
        msg.attach(MIMEText(html_content, 'html'))
        
        # Send email via Hostinger SMTP
        print("Connecting to SMTP server...")
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
            print("Logging in...")
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            print("Sending email...")
            server.send_message(msg)
        
        print("\n" + "="*70)
        print("✅ TEST EMAIL SENT SUCCESSFULLY!")
        print("="*70)
        print(f"Check {TEST_EMAIL} for the email")
        print("="*70 + "\n")
        return True
        
    except Exception as e:
        print("\n" + "="*70)
        print("❌ TEST EMAIL FAILED")
        print("="*70)
        print(f"Error: {e}")
        print("="*70 + "\n")
        return False

if __name__ == "__main__":
    send_test_email()
