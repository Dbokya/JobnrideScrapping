"""
Greenhouse ATS public API scraper.
No API key required. Covers 100+ major companies.
API: https://boards-api.greenhouse.io/v1/boards/{company}/jobs?content=true
"""
import requests
import time
from normalizer import (
    normalize_experience, normalize_job_type, classify_job_for,
    clean_html, normalize_location, normalize_salary, normalize_skills,
    build_description,
)

SOURCE = "greenhouse"

# Company slugs — add more as needed
COMPANIES = [
    # ── India IT Services ─────────────────────────────────────────────────
    "tcs", "infosys", "wipro", "hcl", "tech-mahindra",
    "mphasis", "hexaware", "persistent", "kpit", "ltimindtree",
    "coforge", "zensar", "mastek", "birlasoft", "cyient",
    "tata-elxsi", "sasken", "sonata-software", "niit-technologies",
    # ── India Product / Startup ───────────────────────────────────────────
    "swiggy", "zomato", "flipkart", "paytm", "phonepe",
    "razorpay", "cred", "zepto", "meesho", "ola",
    "nykaa", "sharechat", "dailyhunt", "oyo", "delhivery",
    "postman", "browserstack", "freshworks", "chargebee", "clevertap",
    "darwinbox", "hasura", "setu", "smallcase", "cashfree",
    "moengage", "leadsquared", "pubmatic", "inmobi",
    "groww", "upstox", "zerodha", "angelone", "5paisa",
    "kreditbee", "navi", "jupiter-money", "fi-money", "niyo",
    "slice", "lendingkart", "capital-float",
    "byjus", "unacademy", "vedantu", "upgrad", "simplilearn",
    "scaler", "practo", "pharmeasy", "1mg", "healthifyme",
    "shiprocket", "ecom-express", "porter", "shadowfax",
    "cars24", "droom", "spinny", "cardekho",
    "urban-company", "lenskart", "purplle",
    "innovaccer", "healthplix", "redcliffe-labs",
    "sprinklr", "druva", "icertis", "elastic-run",
    "pixis", "sarvam-ai", "krutrim",
    # ── MNCs India presence ───────────────────────────────────────────────
    "google-india", "microsoft-india", "amazon-india",
    "meta-india", "adobe-india", "oracle-india", "sap-india",
    "ibm-india", "accenture-india", "deloitte-india",
    # Global Tech
    "stripe", "notion", "figma", "airbnb", "shopify", "reddit",
    "coinbase", "discord", "duolingo", "robinhood", "ramp",
    "rippling", "brex", "plaid", "databricks", "snowflake",
    "hashicorp", "mongodb", "elastic", "twilio", "zendesk",
    "intercom", "hubspot", "datadog", "pagerduty", "cloudflare",
    "fastly", "netlify", "grafana", "sentry", "segment",
    "mixpanel", "amplitude", "contentful", "algolia", "auth0",
    "okta", "workos", "launchdarkly", "split", "statsig",
    "retool", "airtable", "webflow", "zapier", "make",
    "clickup", "linear", "loom", "miro", "figma",
    "grammarly", "canva", "deel", "remote", "rippling",
    "gusto", "lattice", "culture-amp", "leapsome",
    "greenhouse", "lever", "ashby",
    # Finance / Fintech
    "affirm", "klarna", "chime", "robinhood", "wealthsimple",
    # Healthcare
    "hinge-health", "lyra-health",
    # E-commerce
    "faire", "recharge", "shipbob",
]


def fetch_jobs(company_slug: str, retries: int = 3) -> list:
    url = f"https://boards-api.greenhouse.io/v1/boards/{company_slug}/jobs?content=true"
    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(url, timeout=15, headers={"User-Agent": "JobNRideBot/2.0"})
            if resp.status_code == 200:
                data = resp.json()
                return data.get("jobs", [])
            if resp.status_code == 404:
                return []  # company not on greenhouse
            print(f"  ⚠ Greenhouse {company_slug}: HTTP {resp.status_code}")
            return []
        except requests.exceptions.RequestException as e:
            wait = 2 ** attempt
            print(f"  ⚠ Network error for {company_slug} (attempt {attempt}): {e}. Retrying in {wait}s...")
            time.sleep(wait)
    return []


def parse_job(raw: dict, company_slug: str) -> dict:
    title = raw.get("title", "").strip()
    apply_link = raw.get("absolute_url", "")
    location_data = raw.get("location", {})
    location = normalize_location(location_data.get("name", "") if isinstance(location_data, dict) else str(location_data))

    content_html = raw.get("content", "") or ""
    description_text = clean_html(content_html)

    # Extract metadata blocks
    metadata = raw.get("metadata", []) or []
    experience_raw = ""
    job_type_raw = ""
    salary_raw = ""
    for meta in metadata:
        name = (meta.get("name") or "").lower()
        value = str(meta.get("value") or "")
        if any(w in name for w in ["experience", "exp"]):
            experience_raw = value
        if any(w in name for w in ["type", "employment"]):
            job_type_raw = value
        if any(w in name for w in ["salary", "ctc", "compensation", "pay"]):
            salary_raw = value

    # Company name from departments or slug
    departments = raw.get("departments", []) or []
    company_name = company_slug.replace("-", " ").title()

    job_for = classify_job_for(title, description_text)
    experience = normalize_experience(experience_raw) if experience_raw else (
        "0-2 years" if job_for in ["intern", "fresher"] else "Not Specified"
    )

    return {
        "title": title,
        "company": company_name,
        "location": location,
        "experience": experience,
        "jobType": normalize_job_type(job_type_raw) if job_type_raw else (
            "Internship" if job_for == "intern" else "Full-Time"
        ),
        "salary": normalize_salary(salary_raw),
        "description": description_text[:5000] if description_text else "No description available.",
        "requirements": "Not Specified",
        "preferredSkills": "Not Specified",
        "responsibilities": "Not Specified",
        "applyLink": apply_link,
        "featuredImage": "",
        "source": f"greenhouse/{company_slug}",
        "jobFor": job_for,
        "country": "",
        "category": departments[0].get("name", "") if departments else "",
        "rawPostedDate": raw.get("updated_at") or raw.get("created_at") or "",
    }


def scrape() -> list:
    all_jobs = []
    print(f"\n🌿 Greenhouse: Scraping {len(COMPANIES)} companies...")
    for company in COMPANIES:
        raw_jobs = fetch_jobs(company)
        if not raw_jobs:
            continue
        print(f"  ✓ {company}: {len(raw_jobs)} jobs")
        for raw in raw_jobs:
            try:
                job = parse_job(raw, company)
                if job["title"] and job["applyLink"]:
                    all_jobs.append(job)
            except Exception as e:
                print(f"  ⚠ Parse error for {company}: {e}")
        time.sleep(0.3)
    print(f"  → Greenhouse total: {len(all_jobs)} jobs")
    return all_jobs
