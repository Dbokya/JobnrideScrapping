
Explanation:

- requests → API fetching
- firebase-admin → Firestore + FCM
- beautifulsoup4 → fallback parsing
- pytz → timezone handling
- google-generativeai → optional AI cleanup

---

# 🔐 REQUIRED GITHUB SECRETS

Go to:

Settings → Secrets and variables → Actions

Add:

1️⃣ FIREBASE_SERVICE_ACCOUNT  
Paste full Firebase service account JSON (single line)

2️⃣ GEMINI_API_KEY (only if AI enabled)

---

# 🧪 TESTING MODE

For testing:

The script can:
- Fetch only the latest job
- Add only one job
- Log all fields added
- Send notification for that job only

Useful before enabling full automation.

---

# 💰 COST STRUCTURE

| Component | Cost |
|------------|-------|
| GitHub Actions | Free |
| Firebase Firestore | Free Tier |
| Firebase FCM | Free |
| AI Cleanup | Free tier |

Total Monthly Cost:
₹0

---

# 🛠 TECHNOLOGY STACK

- Python
- Firebase Admin SDK
- Firestore (nam5 region)
- Firebase Cloud Messaging
- GitHub Actions
- Optional Gemini AI

---

# 📌 WHY THIS ARCHITECTURE?

- No paid VPS
- No server maintenance
- Fully automated
- Scalable
- Duplicate-safe
- Real-time notifications

---

# ✅ CURRENT STATUS

✔ Fetching working  
✔ Duplicate prevention working  
✔ Firestore saving working  
✔ FCM sending working  
✔ GitHub cron running  
✔ Free infrastructure  

---

# 📈 FUTURE IMPROVEMENTS

- Add job categorization AI
- Add keyword filtering
- Add salary extraction logic
- Add job expiration handling
- Add analytics logging

---

# 👨‍💻 Maintained For

JobnRide Mobile Application  
Package: com.kdads.jobnride  

---

End of Documentation
