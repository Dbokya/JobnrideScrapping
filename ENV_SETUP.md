# JobNRide Scrapping - Environment Variables

## Required Environment Variables

### For Local Development:

1. **OPEN_AI_API_KEY**: Your OpenAI API key
   - Set in PowerShell: `$env:OPEN_AI_API_KEY="your-api-key-here"`
   - Or create a `.env` file and load it

### For GitHub Actions:

The following secrets must be configured in GitHub repository settings:

1. **OPEN_AI_API_KEY**: OpenAI API key for job content analysis
2. **FIREBASE_KEY**: Firebase Admin SDK service account JSON content

## Local Setup

```powershell
# Set environment variable for current session
$env:OPEN_AI_API_KEY="your-openai-api-key"

# Run the scraper
python scrape_jobcode_to_firestore.py
```

## GitHub Actions Setup

1. Go to repository Settings → Secrets and variables → Actions
2. Add the required secrets:
   - `OPEN_AI_API_KEY`
   - `FIREBASE_KEY`

The workflow runs automatically every 2 hours or can be triggered manually.
