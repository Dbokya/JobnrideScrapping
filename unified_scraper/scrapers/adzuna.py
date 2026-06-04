"""
Adzuna API scraper.
Free tier: 250 calls/day. Covers India, UK, US, AU, CA, SG, AE.
Register free at: https://developer.adzuna.com/
Env vars: ADZUNA_APP_ID, ADZUNA_APP_KEY
"""
import os
import re
import requests
import time
from datetime import datetime, timezone
from normalizer import (
    normalize_job_type, classify_job_for,
    clean_html, normalize_location, normalize_salary,
    normalize_work_mode, extract_education, infer_functional_area, infer_industry,
    extract_skills_from_text,
)

SOURCE = "adzuna"

APP_ID = os.getenv("ADZUNA_APP_ID", "")
APP_KEY = os.getenv("ADZUNA_APP_KEY", "")

# India only — remote jobs appear in India results too
COUNTRIES = {
    "in": "India",
}

RESULTS_PER_PAGE = 50

# ── Quota management ─────────────────────────────────────────────────────────
# Adzuna free tier = 250 API calls/day. The GitHub Action runs 6×/day (every
# 4h), so each run gets a budget of ~250/6 ≈ 41 calls. To cover ALL companies
# daily without blowing quota, the company list is ROTATED across the 6 runs:
# each run handles 1/NUM_SLOTS of COMPANY_TERMS, chosen by the clock hour, so
# every company is searched exactly once per day.
#   per-run calls ≈ (KEYWORD_TERMS * MAX_PAGES_KEYWORD)
#                 + (ceil(len(COMPANY_TERMS)/NUM_SLOTS) * MAX_PAGES_COMPANY)
NUM_SLOTS = 6           # number of scheduled runs per day (matches workflow cron)
MAX_PAGES_KEYWORD = 2   # 2 pages = 100 newest jobs per keyword
MAX_PAGES_COMPANY = 1   # 1 page  = 50 newest jobs per company
KEYWORD_TERMS = 8       # use first N keyword terms each run

# IT job search terms for India (broad coverage across ALL companies)
SEARCH_TERMS = [
    "software engineer", "data engineer", "product manager",
    "frontend developer", "backend developer", "devops engineer",
    "data scientist", "machine learning engineer", "mobile developer",
    "full stack developer", "cloud engineer", "qa engineer",
    "solution architect", "java developer", "python developer",
    "react developer", "node.js developer", "android developer",
    "ios developer", "flutter developer",
]

# Big IT-services / MNC employers that have NO public ATS API — Adzuna is the
# only way to reach them. We search by company name and keep only jobs whose
# advertised company actually matches. Companies already covered by a live ATS
# board (greenhouse/lever/ashby/smartrecruiters/recruitee) are intentionally
# left OUT here to avoid duplicate postings. Extend freely.
COMPANY_TERMS = [
    # ── Tier-1 / Tier-2 IT services ──────────────────────────────────────────
    "Amdocs", "Cognizant", "Capgemini", "Accenture", "Infosys", "Wipro",
    "TCS", "Tata Consultancy", "HCLTech", "Tech Mahindra", "Mphasis",
    "LTIMindtree", "Persistent Systems", "Coforge", "Birlasoft", "Cyient",
    "KPIT", "Zensar", "Mastek", "Nagarro", "EPAM", "Globant", "Luxoft",
    "GlobalLogic", "Encora", "Brillio", "Hexaware", "Sonata Software",
    "Happiest Minds", "Tata Elxsi", "L&T Technology Services",
    "Mindtree", "NIIT Technologies", "DXC Technology", "Unisys",
    "Tata Technologies", "Quest Global", "Cigniti", "Newgen Software",
    "Nucleus Software", "Intellect Design Arena", "Subex", "Saksoft",
    "R Systems", "Cybage", "Xoriant", "Yash Technologies", "Trigent",
    "Onward Technologies", "Sasken Technologies", "3i Infotech",
    # ── BPO / ITES ───────────────────────────────────────────────────────────
    "Genpact", "WNS Global", "Firstsource", "Sutherland", "eClerx",
    "Conduent", "Hinduja Global", "Teleperformance", "Concentrix", "Infosys BPM",
    # ── Consulting / Big 4 / analytics ───────────────────────────────────────
    "Deloitte", "PwC", "EY", "KPMG", "Sapient", "Publicis Sapient",
    "Tiger Analytics", "Fractal Analytics", "Mu Sigma", "LatentView",
    "ZS Associates", "Tredence", "Quantiphi", "Affine", "Course5", "Gramener",
    "McKinsey", "BCG", "Bain",
    # ── GCC / captive / MNC product & dev centres in India ───────────────────
    "IBM", "Oracle", "SAP Labs", "Adobe", "Salesforce", "ServiceNow",
    "VMware", "Cisco", "Qualcomm", "Nvidia", "Intel", "AMD", "Micron",
    "Samsung", "Dell Technologies", "Walmart Global Tech", "Google",
    "Microsoft", "Amazon", "Uber", "Expedia", "Target Corporation", "Lowe's",
    "Tesco", "Maersk", "Optum", "Fidelity Investments", "Goldman Sachs",
    "JPMorgan", "Morgan Stanley", "Wells Fargo", "American Express",
    "Mastercard", "Visa", "PayPal", "Barclays", "HSBC", "Standard Chartered",
    "Citi", "Deutsche Bank", "Nomura", "Bank of America",
    "Ericsson", "Nokia", "Bosch", "Siemens", "Honeywell", "Schneider Electric",
    # ── Indian enterprises / unicorns without a working ATS board ────────────
    "Flipkart", "Swiggy", "Zomato", "Razorpay", "Nykaa", "Ola", "OYO",
    "Zerodha", "Dream11", "Delhivery", "Udaan", "Urban Company", "Lenskart",
    "BigBasket", "Zepto", "PharmEasy", "Unacademy", "PhonePe", "Paytm",
]


def fetch_page(country: str, search: str, page: int, retries: int = 3) -> list:
    if not APP_ID or not APP_KEY:
        return []
    url = f"https://api.adzuna.com/v1/api/jobs/{country}/search/{page}"
    params = {
        "app_id": APP_ID,
        "app_key": APP_KEY,
        "results_per_page": RESULTS_PER_PAGE,
        "what": search,
        "content-type": "application/json",
    }
    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(url, params=params, timeout=20, headers={"User-Agent": "JobNRideBot/2.0"})
            if resp.status_code == 200:
                return resp.json().get("results", [])
            if resp.status_code == 401:
                print("  ⚠ Adzuna: Invalid API credentials. Set ADZUNA_APP_ID and ADZUNA_APP_KEY.")
                return []
            print(f"  ⚠ Adzuna {country}: HTTP {resp.status_code}")
            return []
        except requests.exceptions.RequestException as e:
            wait = 2 ** attempt
            print(f"  ⚠ Adzuna error (attempt {attempt}): {e}. Retry in {wait}s...")
            time.sleep(wait)
    return []


def parse_job(raw: dict, country_name: str) -> dict:
    title = raw.get("title", "").strip()
    company_data = raw.get("company", {}) or {}
    company = company_data.get("display_name", "").strip()
    location_data = raw.get("location", {}) or {}
    location_areas = location_data.get("area", []) or []
    location = normalize_location(", ".join(location_areas[-2:]) if location_areas else country_name)

    salary_min = raw.get("salary_min")
    salary_max = raw.get("salary_max")
    if salary_min and salary_max:
        salary = f"{salary_min:,.0f} - {salary_max:,.0f}"
    elif salary_min:
        salary = f"{salary_min:,.0f}+"
    else:
        salary = "Not Disclosed"

    description_html = raw.get("description", "")
    description_text = clean_html(description_html)
    apply_link = raw.get("redirect_url", "")
    category_data = raw.get("category", {}) or {}
    category = category_data.get("label", "")
    contract_type = raw.get("contract_type", "")
    contract_time = raw.get("contract_time", "")

    job_for = classify_job_for(title, description_text)

    job_type = normalize_job_type(contract_type or contract_time)
    company_name = company or "Not Specified"
    
    # Extract skills from description and category
    skills_text = extract_skills_from_text(description_text)
    if not skills_text or skills_text == "Not Specified":
        skills_text = extract_skills_from_text(category)

    return {
        "title": title,
        "company": company_name,
        "location": location,
        "experience": "0-2 years" if job_for in ["intern", "fresher"] else "Not Specified",
        "jobType": job_type,
        "salary": salary,
        "description": description_text[:5000] if description_text else "No description available.",
        "requirements": "Not Specified",
        "preferredSkills": skills_text,
        "responsibilities": "Not Specified",
        "applyLink": apply_link,
        "featuredImage": "",
        "source": f"adzuna/{country_name.lower()}",
        "jobFor": job_for,
        "country": country_name,
        "category": category,
        "workMode": normalize_work_mode(location, job_type),
        "functionalArea": infer_functional_area(title, category, description_text),
        "industry": infer_industry(company_name, category, title),
        "educationRequirement": extract_education(description_text),
        "noticePeriod": "Not Specified",
        "totalOpenings": "Not Specified",
        "benefits": "",
        "aboutCompany": "",
        "notificationTitle": f"New Job at {company_name}",
        "rawPostedDate": raw.get("created") or raw.get("date") or "",
    }


def _collect(country_code, country_name, search, max_pages, company_filter=None):
    """Fetch jobs for one search term; optionally keep only matching company."""
    jobs = []
    needle = re.compile(rf"\b{re.escape(company_filter)}\b", re.I) if company_filter else None
    for page in range(1, max_pages + 1):
        raw_jobs = fetch_page(country_code, search, page)
        if not raw_jobs:
            break
        for raw in raw_jobs:
            try:
                job = parse_job(raw, country_name)
                if not (job["title"] and job["company"] != "Not Specified" and job["applyLink"]):
                    continue
                if needle and not needle.search(job["company"]):
                    continue
                jobs.append(job)
            except Exception as e:
                print(f"  ⚠ Adzuna parse error: {e}")
        time.sleep(0.4)
    return jobs


def scrape() -> list:
    if not APP_ID or not APP_KEY:
        print("\n⚠️  Adzuna: Skipping — ADZUNA_APP_ID and ADZUNA_APP_KEY not set.")
        print("   Get free API keys at https://developer.adzuna.com/")
        return []

    all_jobs = []

    # Pick this run's company slice by clock hour so all firms are covered once
    # per day across the NUM_SLOTS scheduled runs (no shared state needed).
    slot = (datetime.now(timezone.utc).hour // (24 // NUM_SLOTS)) % NUM_SLOTS
    company_slice = COMPANY_TERMS[slot::NUM_SLOTS]
    calls_run = (KEYWORD_TERMS * MAX_PAGES_KEYWORD) + (len(company_slice) * MAX_PAGES_COMPANY)
    print(f"\n📊 Adzuna: run slot {slot + 1}/{NUM_SLOTS} — keywords + "
          f"{len(company_slice)} companies (~{calls_run} calls this run)...")

    for country_code, country_name in COUNTRIES.items():
        # ── Phase 1: broad keyword coverage (any company), every run ─────────
        kw_jobs = []
        for search in SEARCH_TERMS[:KEYWORD_TERMS]:
            kw_jobs.extend(_collect(country_code, country_name, search, MAX_PAGES_KEYWORD))
        print(f"  ✓ {country_name} keywords: {len(kw_jobs)} jobs")
        all_jobs.extend(kw_jobs)

        # ── Phase 2: this run's company slice (IT-services giants w/o ATS) ───
        co_jobs = []
        for company in company_slice:
            hits = _collect(country_code, country_name, company, MAX_PAGES_COMPANY,
                            company_filter=company)
            if hits:
                co_jobs.extend(hits)
        print(f"  ✓ {country_name} companies: {len(co_jobs)} jobs "
              f"(from {len(company_slice)} firms this slot)")
        all_jobs.extend(co_jobs)

    print(f"  → Adzuna total: {len(all_jobs)} jobs")
    return all_jobs
