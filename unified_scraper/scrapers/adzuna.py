"""
Adzuna API scraper.
Free tier: 250 calls/day. Covers India, UK, US, AU, CA, SG, AE.
Register free at: https://developer.adzuna.com/
Env vars: ADZUNA_APP_ID, ADZUNA_APP_KEY
"""
import os
import requests
import time
from normalizer import (
    normalize_job_type, classify_job_for,
    clean_html, normalize_location, normalize_salary,
)

SOURCE = "adzuna"

APP_ID = os.getenv("ADZUNA_APP_ID", "")
APP_KEY = os.getenv("ADZUNA_APP_KEY", "")

# India only — remote jobs appear in India results too
COUNTRIES = {
    "in": "India",
}

RESULTS_PER_PAGE = 50
MAX_PAGES_PER_COUNTRY = 5  # 250 jobs per search term

# IT job search terms for India
SEARCH_TERMS = [
    "software engineer", "data engineer", "product manager",
    "frontend developer", "backend developer", "devops engineer",
    "data scientist", "machine learning engineer", "mobile developer",
    "full stack developer", "cloud engineer", "qa engineer",
    "solution architect", "java developer", "python developer",
    "react developer", "node.js developer", "android developer",
    "ios developer", "flutter developer",
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

    return {
        "title": title,
        "company": company or "Not Specified",
        "location": location,
        "experience": "0-2 years" if job_for in ["intern", "fresher"] else "Not Specified",
        "jobType": normalize_job_type(contract_type or contract_time),
        "salary": salary,
        "description": description_text[:5000] if description_text else "No description available.",
        "requirements": "Not Specified",
        "preferredSkills": "Not Specified",
        "responsibilities": "Not Specified",
        "applyLink": apply_link,
        "featuredImage": "",
        "source": f"adzuna/{country_name.lower()}",
        "jobFor": job_for,
        "country": country_name,
        "category": category,
        "rawPostedDate": raw.get("created") or raw.get("date") or "",
    }


def scrape() -> list:
    if not APP_ID or not APP_KEY:
        print("\n⚠️  Adzuna: Skipping — ADZUNA_APP_ID and ADZUNA_APP_KEY not set.")
        print("   Get free API keys at https://developer.adzuna.com/")
        return []

    all_jobs = []
    print(f"\n📊 Adzuna: Fetching jobs across {len(COUNTRIES)} countries...")

    for country_code, country_name in COUNTRIES.items():
        country_jobs = []
        for search in SEARCH_TERMS[:8]:  # up to 8 search terms for India
            for page in range(1, MAX_PAGES_PER_COUNTRY + 1):
                raw_jobs = fetch_page(country_code, search, page)
                if not raw_jobs:
                    break
                for raw in raw_jobs:
                    try:
                        job = parse_job(raw, country_name)
                        if job["title"] and job["company"] != "Not Specified" and job["applyLink"]:
                            country_jobs.append(job)
                    except Exception as e:
                        print(f"  ⚠ Adzuna parse error: {e}")
                time.sleep(0.4)
        print(f"  ✓ {country_name}: {len(country_jobs)} jobs")
        all_jobs.extend(country_jobs)

    print(f"  → Adzuna total: {len(all_jobs)} jobs")
    return all_jobs
