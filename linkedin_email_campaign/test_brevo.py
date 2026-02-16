import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os

# Brevo Configuration
SMTP_SERVER = "smtp-relay.brevo.com"
SMTP_PORT = 587  # STARTTLS
SENDER_EMAIL = "support@jobnride.com"
BREVO_API_KEY = os.getenv("BREVO_API_KEY")
BREVO_LOGIN = os.getenv("BREVO_LOGIN", SENDER_EMAIL)  # Brevo might need specific login
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

def test_brevo():
    """Test Brevo SMTP connection and send a test email"""
    
    if not BREVO_API_KEY:
        print("❌ ERROR: BREVO_API_KEY environment variable not set")
        print("Set it using: $env:BREVO_API_KEY='your-smtp-key'")
        return False

    # sanitize env inputs
    brevo_key = BREVO_API_KEY.strip()
    brevo_login = (BREVO_LOGIN or SENDER_EMAIL).strip()
    
    print("\n" + "="*70)
    print("TESTING BREVO EMAIL")
    print("="*70)
    print(f"Server: {SMTP_SERVER}:{SMTP_PORT}")
    print(f"Login: {BREVO_LOGIN}")
    print(f"From: {SENDER_EMAIL}")
    print(f"To: {TEST_EMAIL}")
    def mask(s):
        if not s:
            return ''
        if len(s) <= 12:
            return s[:2] + '...' + s[-2:]
        return s[:6] + '...' + s[-4:]

    print(f"API Key: {mask(brevo_key)}")
    print("="*70 + "\n")
    
    try:
        # Create message
        msg = MIMEMultipart('alternative')
        msg['From'] = f"{SENDER_NAME} <{SENDER_EMAIL}>"
        msg['To'] = TEST_EMAIL
        msg['Subject'] = "Exclusive Job Opportunities with JobNRide - Your Career Partner (via Brevo)"
        
        # Attach HTML content
        html_content = get_email_template()
        msg.attach(MIMEText(html_content, 'html'))
        
        # Try several connection/auth permutations to help diagnose 535 errors
        attempts = []
        servers = [
            ("smtp-relay.brevo.com", 587, False),  # STARTTLS
            ("smtp-relay.brevo.com", 465, True),   # SSL
            ("smtp.brevo.com", 465, True),         # alternate host
        ]
        usernames = [brevo_login, 'apikey', SENDER_EMAIL]

        last_exc = None
        for host, port, use_ssl in servers:
            for username in usernames:
                attempt_desc = f"{host}:{port} ssl={use_ssl} user={username}"
                print('\n' + '-'*60)
                print(f"Attempting: {attempt_desc}")
                try:
                    if use_ssl:
                        server = smtplib.SMTP_SSL(host, port, timeout=20)
                    else:
                        server = smtplib.SMTP(host, port, timeout=20)
                    server.set_debuglevel(1)

                    if not use_ssl:
                        print("Starting TLS...")
                        server.starttls()

                    print(f"Logging in as: {username} (password masked: {mask(brevo_key)})")
                    server.login(username, brevo_key)
                    print("Login succeeded — sending email...")
                    server.send_message(msg)
                    server.quit()
                    print("SUCCESS: Email sent using", attempt_desc)
                    return True
                except Exception as e:
                    last_exc = e
                    print(f"FAILED: {attempt_desc} — {e}")
                    try:
                        server.quit()
                    except Exception:
                        pass

        # If we reached here, all attempts failed
        raise last_exc
        
        print("\n" + "="*70)
        print("BREVO TEST EMAIL SENT SUCCESSFULLY!")
        print("="*70)
        print(f"Brevo connection working")
        print(f"Check {TEST_EMAIL} for the email")
        print(f"Ready to send emails via Brevo!")
        print("="*70 + "\n")
        return True
        
    except Exception as e:
        print("\n" + "="*70)
        print("BREVO TEST FAILED")
        print("="*70)
        print(f"Final error: {e}")
        print("\nTroubleshooting steps:")
        print("- Ensure the SMTP key (xsmtpsib-...) is used as the password (BREVO_API_KEY).")
        print("- Confirm the SMTP login (BREVO_LOGIN) exactly matches Brevo's displayed login (eg 9fb24b001@smtp-brevo.com).")
        print("- Verify the sender email (support@jobnride.com) is added/verified in Brevo Senders.")
        print("- If auth still fails, generate a new SMTP key in Brevo and retry.")
        print("- Consider testing with a different host/port combination shown above.")
        print("="*70 + "\n")
        return False

if __name__ == "__main__":
    test_brevo()
