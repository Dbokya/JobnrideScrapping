# 📧 LinkedIn Email Campaign

The email automation system for LinkedIn outreach has been moved to its own folder:

👉 **[linkedin_email_campaign/](linkedin_email_campaign/)**

## 🚀 New: Send 200 Emails Per Day!

Use **both Hostinger and Brevo** to double your capacity:
- **Hostinger:** 100 emails/day ✅
- **Brevo:** 100 emails/day ✅
- **Total:** 200 emails/day 🎯

## Quick Start

**Option 1: Multi-Provider (200/day)**
```powershell
cd linkedin_email_campaign
python send_emails_multi_provider.py
# Select provider when prompted
```

**Option 2: Single Provider (100/day)**
```powershell
cd linkedin_email_campaign
python send_user_emails.py
```

## Documentation

- 📖 [README.md](linkedin_email_campaign/README.md) - Main documentation
- 🔄 [MULTI_PROVIDER_GUIDE.md](linkedin_email_campaign/MULTI_PROVIDER_GUIDE.md) - Use both providers

## Files in This Folder

- `send_emails_multi_provider.py` - **NEW!** Multi-provider support (Hostinger + Brevo)
- `send_user_emails.py` - Single provider (Hostinger only)
- `test_email.py` - Send test email
- `README.md` - Complete documentation
- `MULTI_PROVIDER_GUIDE.md` - Multi-provider setup guide
- `users_template.xlsx` - Sample user data format
- `users.xlsx` - Your actual user data (not committed to git)

## What It Does

1. ✅ Checks Firebase for existing JobNRide users
2. ✅ Separates new prospects from existing users
3. ✅ Sends personalized emails (200/day with both providers)
4. ✅ Tracks progress automatically
5. ✅ No duplicate emails across providers
