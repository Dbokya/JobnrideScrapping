# JobNRide User Email Campaign

Send personalized emails to users who shared their contact information on LinkedIn for job opportunities.

## 🚀 New: Multi-Provider Support!

**Send 200 emails per day** instead of 100 by using both Hostinger and Brevo!

👉 **See [MULTI_PROVIDER_GUIDE.md](MULTI_PROVIDER_GUIDE.md) for details**

Quick start with multi-provider:
```powershell
python send_emails_multi_provider.py
```

## Features

- ✅ **Firebase Integration** - Automatically checks if users already have accounts
- ✅ **Smart Categorization** - Separates existing users from new prospects
- ✅ **Multi-Provider Support** - Use Hostinger + Brevo for 200 emails/day
- ✅ Respects daily limits (100 per provider)
- ✅ Tracks sent emails to avoid duplicates
- ✅ Professional HTML email template
- ✅ Progress tracking and statistics
- ✅ Automatic retry and error handling

## How It Works

The script performs these steps:

1. **Reads** `users.xlsx` with all LinkedIn contacts
2. **Checks Firebase** to see which emails already have JobNRide accounts
3. **Categorizes** users into two files:
   - `users_with_accounts.xlsx` - Users who already registered (no email needed)
   - `users_to_email.xlsx` - New users who need invitation emails
4. **Sends emails** only to new users (up to 100/day limit)
5. **Updates** `users_to_email.xlsx` with timestamps

## Setup

### 1. Environment Variable

Set your Hostinger email password as an environment variable:

**PowerShell:**
```powershell
$env:EMAIL_PASSWORD="your-hostinger-email-password"
```

**Linux/Mac:**
```bash
export EMAIL_PASSWORD="your-hostinger-email-password"
```

### 2. User Data File

Ensure `users.xlsx` exists with the following columns:
- `name` - User name (optional)
- `email` - User email address (required)
- `accountCreated` - Account creation timestamp (optional)
- `lastEmailSent` - Last email sent timestamp (auto-updated)

## Usage

Run the script:
```powershell
python send_user_emails.py
```

The script will:
1. Check Firebase for existing accounts
2. Create `users_with_accounts.xlsx` and `users_to_email.xlsx`
3. Show categorization summary
4. Send emails to new users (up to 100/day)
5. Update timestamps in `users_to_email.xlsx`

## Output Files

**users_with_accounts.xlsx** - Users who already have JobNRide accounts
- These users won't receive emails (they're already using the app!)
- Useful for analytics

**users_to_email.xlsx** - New users who need invitation emails
- Only these users will receive emails
- Timestamps are tracked here

## Email Template

The email includes:
- Personalized greeting
- JobNRide app introduction
- Key features (job alerts, referrals, off-campus drives)
- Download links for Android & iOS
- Professional signature with contact details

## Example Output

```
======================================================================
🔍 CATEGORIZING USERS - CHECKING FIREBASE ACCOUNTS
======================================================================

Checking 166 users against Firebase...
✓ Found in Firebase: user1@gmail.com
○ New user: user2@gmail.com
✓ Found in Firebase: user3@gmail.com
...

======================================================================
📊 CATEGORIZATION COMPLETE
======================================================================
✓ Users with accounts: 45 (saved to users_with_accounts.xlsx)
○ New users to email: 121 (saved to users_to_email.xlsx)
======================================================================

======================================================================
📧 JOBNRIDE - USER EMAIL CAMPAIGN
======================================================================
Total new users: 121
Users pending emails: 121
Emails to send today: 100 (Limit: 100)
======================================================================

Send 100 emails? (yes/no): yes

✓ Sent to: newuser1@gmail.com
✓ Sent to: newuser2@gmail.com
...

======================================================================
📊 CAMPAIGN SUMMARY
======================================================================
✓ Successfully sent: 100
✗ Failed: 0
📝 Updated users_to_email.xlsx with timestamps
======================================================================

ℹ️  21 users remaining for next batch
```

## SMTP Configuration

**Hostinger Settings (Pre-configured):**
- Server: `smtp.hostinger.com`
- Port: `465` (SSL)
- Sender: `durgesh.tiwari@jobnride.com`

## Important Notes

⚠️ **Daily Limit**: Hostinger allows 100 emails per day. The script enforces this limit automatically.

## Important Notes

⚠️ **Daily Limit**: Hostinger allows 100 emails per day. The script enforces this limit automatically.

⚠️ **Firebase Check**: The script checks Firebase on EVERY run to ensure the most up-to-date categorization. If a user registers between runs, they'll be moved to `users_with_accounts.xlsx` automatically.

⚠️ **Tracking**: The script updates `users_to_email.xlsx` after each batch. Don't delete or modify the `lastEmailSent` column manually.

⚠️ **Rate Limiting**: 1-second delay between emails to avoid triggering spam filters.

## Troubleshooting

**Error: EMAIL_PASSWORD environment variable not set**
- Solution: Set the environment variable before running the script

**Error: Could not read users.xlsx**
- Solution: Ensure the file exists in the same directory as the script

**Firebase connection errors**
- Verify serviceaccount/jobnride-97d77-firebase-adminsdk-fbsvc-20ce6e6129.json exists
- Check internet connection
- Ensure Firebase credentials are valid

**Failed to send emails**
- Check your internet connection
- Verify Hostinger SMTP credentials
- Check if the email address is valid

## Example Workflow

**Initial Run:**
- 166 total users in `users.xlsx`
- Firebase check finds 45 users already have accounts
- 121 new users need emails

**Day 1:**
- Send 100 emails to new users
- 21 users remaining

**Day 2:**
- Firebase check runs again (some users may have registered!)
- Send remaining 21 emails
- Campaign complete! 🎉

## Why Firebase Checking?

Users who already have JobNRide accounts don't need "download the app" emails. By checking Firebase first, we:
- ✅ Avoid sending redundant emails
- ✅ Save email quota for actual prospects
- ✅ Maintain professional communication
- ✅ Track which LinkedIn contacts converted to users
