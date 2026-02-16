# 🔄 Multi-Provider Email Campaign

Send emails using **two providers** to maximize your daily sending capacity!

## Providers Supported

1. **Hostinger** - 100 emails/day ✅ (Already configured)
2. **Brevo (Sendinblue)** - 100 emails/day ✅ (Ready to use)

**Total Capacity: 200 emails per day!**

## Setup

### Hostinger (Already Working)
```powershell
# Already configured - no additional setup needed
```

### Brevo Setup (For Next 100 Emails)

1. **Get your Brevo SMTP API Key:**
   - Login to [Brevo](https://app.brevo.com)
   - Go to: SMTP & API → SMTP
   - Copy your SMTP API Key

2. **Set environment variable:**
   ```powershell
   $env:BREVO_API_KEY="your-brevo-smtp-api-key"
   ```

3. **(Optional) Set custom sender email:**
   ```powershell
   $env:BREVO_SENDER_EMAIL="support@jobnride.com"
   ```

## Usage

### Run the Multi-Provider Script:
```powershell
cd linkedin_email_campaign
python send_emails_multi_provider.py
```

### Workflow:

**Step 1: Choose Provider**
```
📧 EMAIL PROVIDER SELECTION
======================================================================
1. Hostinger (100 emails/day)
2. Brevo (100 emails/day)
======================================================================
Select provider (1 or 2): 1
```

**Step 2: Script will:**
- Check Firebase for existing users
- Show how many emails to send
- Ask for confirmation
- Send emails using selected provider
- Track which users received emails

## Recommended Strategy

### Day 1 - Hostinger (100 emails)
```powershell
python send_emails_multi_provider.py
# Select: 1 (Hostinger)
# Sends: 100 emails
# Remaining: 66 users
```

### Day 1 (Same Day) - Brevo (66 emails)
```powershell
python send_emails_multi_provider.py
# Select: 2 (Brevo)
# Sends: 66 emails
# Remaining: 0 users
# ✅ All done in one day!
```

## Why Two Providers?

✅ **Double your capacity** - 200 emails/day instead of 100
✅ **Backup option** - If one provider has issues, use the other
✅ **Faster campaigns** - Complete 166 users in one day instead of two
✅ **Redundancy** - Less dependency on single provider

## Configuration Details

### Hostinger
- **Server:** smtp.hostinger.com
- **Port:** 465 (SSL)
- **Email:** support@jobnride.com
- **Limit:** 100/day

### Brevo
- **Server:** smtp-relay.brevo.com
- **Port:** 587 (STARTTLS)
- **Email:** support@jobnride.com (or custom)
- **Limit:** 100/day
- **Free Tier:** 300 emails/day (we use 100 to match Hostinger)

## Tracking

Both providers update the same `users_to_email.xlsx` file, so:
- ✅ No duplicate emails
- ✅ Consistent tracking across providers
- ✅ Can switch between providers seamlessly

## Example Output

```
======================================================================
📧 EMAIL PROVIDER SELECTION
======================================================================
1. Hostinger (100 emails/day)
2. Brevo (100 emails/day)
======================================================================
Select provider (1 or 2): 1

✓ Using Hostinger (support@jobnride.com)

======================================================================
🔍 CATEGORIZING USERS - CHECKING FIREBASE ACCOUNTS
======================================================================

Checking 166 users against Firebase...
✓ Found in Firebase: user1@gmail.com
○ New user: user2@gmail.com
...

======================================================================
📊 CATEGORIZATION COMPLETE
======================================================================
✓ Users with accounts: 45 (saved to users_with_accounts.xlsx)
○ New users to email: 121 (saved to users_to_email.xlsx)
======================================================================

======================================================================
📧 JOBNRIDE - USER EMAIL CAMPAIGN (Hostinger)
======================================================================
Total new users: 121
Users pending emails: 121
Emails to send today: 100 (Limit: 100)
======================================================================

Send 100 emails via Hostinger? (yes/no): yes

✓ Sent to: newuser1@gmail.com
✓ Sent to: newuser2@gmail.com
...

======================================================================
📊 CAMPAIGN SUMMARY (Hostinger)
======================================================================
✓ Successfully sent: 100
✗ Failed: 0
📝 Updated users_to_email.xlsx with timestamps
======================================================================

ℹ️  21 users remaining for next batch
💡 TIP: Use Brevo for the next 21 emails tomorrow!
```

## Quick Reference

| Action | Command |
|--------|---------|
| Send via Hostinger | `python send_emails_multi_provider.py` → Select 1 |
| Send via Brevo | `python send_emails_multi_provider.py` → Select 2 |
| Test email | `python test_email.py` |
| Check Firebase status | Script does this automatically |

## Need Help?

**Brevo API Key not working?**
- Verify you copied the SMTP API key (not REST API key)
- Check if sender email is verified in Brevo

**Want to use only one provider?**
- Use the original `send_user_emails.py` (Hostinger only)
- Or always select the same provider in multi-provider script

---

**🎯 Goal:** Contact all 166 LinkedIn users efficiently using both email providers!
