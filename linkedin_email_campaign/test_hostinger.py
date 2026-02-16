import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

HOST = os.getenv('HOSTINGER_SMTP_SERVER', 'smtp.hostinger.com')
SSL_PORT = int(os.getenv('HOSTINGER_SSL_PORT', 465))
STARTTLS_PORT = int(os.getenv('HOSTINGER_STARTTLS_PORT', 587))
LOGIN = os.getenv('HOSTINGER_LOGIN', 'support@jobnride.com')
PASSWORD = os.getenv('HOSTINGER_PASSWORD')
TEST_TO = os.getenv('TEST_EMAIL', 'kd.adssolution@gmail.com')
SENDER_NAME = os.getenv('HOSTINGER_SENDER_NAME', 'JobNRide')

if not PASSWORD:
    print('ERROR: set HOSTINGER_PASSWORD environment variable to your SMTP password')
    raise SystemExit(1)

msg = MIMEMultipart('alternative')
msg['From'] = f"{SENDER_NAME} <{LOGIN}>"
msg['To'] = TEST_TO
msg['Subject'] = 'Hostinger SMTP diagnostic — JobNRide'
msg.attach(MIMEText('<p>Hostinger SMTP diagnostic test</p>', 'html'))


def try_ssl():
    print('\n-- Trying SSL (465) --')
    try:
        server = smtplib.SMTP_SSL(HOST, SSL_PORT, timeout=20)
        server.set_debuglevel(1)
        server.login(LOGIN, PASSWORD)
        server.send_message(msg)
        server.quit()
        print('SUCCESS: SSL send succeeded')
        return True
    except Exception as e:
        print('SSL attempt failed:', e)
        try:
            server.quit()
        except Exception:
            pass
        return False


def try_starttls():
    print('\n-- Trying STARTTLS (587) --')
    try:
        server = smtplib.SMTP(HOST, STARTTLS_PORT, timeout=20)
        server.set_debuglevel(1)
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(LOGIN, PASSWORD)
        server.send_message(msg)
        server.quit()
        print('SUCCESS: STARTTLS send succeeded')
        return True
    except Exception as e:
        print('STARTTLS attempt failed:', e)
        try:
            server.quit()
        except Exception:
            pass
        return False


if __name__ == '__main__':
    print(f"Host: {HOST} SSL_PORT: {SSL_PORT} STARTTLS_PORT: {STARTTLS_PORT}")
    print(f"Login: {LOGIN}")
    ok_ssl = try_ssl()
    ok_tls = try_starttls()
    print('\nSummary:')
    print('SSL OK:', ok_ssl)
    print('STARTTLS OK:', ok_tls)
    if not ok_ssl and not ok_tls:
        print('\nNext steps:')
        print('- Verify SMTP password is correct and not truncated (no extra spaces).')
        print('- Try logging into webmail with the same credentials to confirm password.')
        print('- Check Hostinger control panel for SMTP-specific password or app password settings.')
        print('- If you use 2FA or special account restrictions, create an app password for SMTP.')
        print('- If still failing, contact Hostinger support and provide the SMTP debug trace above.')
