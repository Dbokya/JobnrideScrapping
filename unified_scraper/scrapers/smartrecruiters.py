"""
SmartRecruiters ATS public API scraper.
No API key required. Many Indian IT companies use SmartRecruiters.
API: https://api.smartrecruiters.com/v1/companies/{company-id}/postings
"""
import requests
import time
from normalizer import (
    normalize_job_type, classify_job_for,
    clean_html, normalize_location,
)

SOURCE = "smartrecruiters"

# Format: (display_name, company_id_slug)
COMPANIES = [
    # Big IT
    ("HCL Technologies",         "HCLTech"),
    ("Cognizant",                "Cognizant"),
    ("Mphasis",                  "Mphasis"),
    ("Hexaware Technologies",    "Hexaware"),
    ("Cyient",                   "Cyient"),
    ("NIIT Technologies",        "NIITTechnologies"),
    ("Mindtree",                 "MindtreeLimited"),
    ("Sasken Technologies",      "Sasken"),
    ("Tata Elxsi",               "TataElxsi"),
    ("LTIMINDTREE",              "LTIMindtree"),
    ("Coforge",                  "Coforge"),
    ("Zensar",                   "ZensarTechnologies"),
    # MNCs in India
    ("Siemens India",            "Siemens"),
    ("Bosch India",              "Bosch"),
    ("ABB India",                "ABBGroup"),
    ("Schneider Electric India", "SchneiderElectric"),
    ("Philips India",            "Philips"),
    ("Honeywell India",          "Honeywell"),
    # Startups / Product
    ("Ola",                      "ANITechnologies"),
    ("Urban Company",            "UrbanCompany"),
    ("Sharechat",                "ShareChat"),
    ("Dailyhunt",                "DailyhuntVerso"),
    ("Nykaa",                    "Nykaa"),
    ("Purplle",                  "Purplle"),
    ("Lenskart",                 "Lenskart"),
    ("Cars24",                   "Cars24"),
    ("Droom",                    "Droom"),
    ("OYO",                      "OYO"),
    ("Zolo",                     "ZoloStays"),
]

PAGE_LIMIT = 100


def fetch_jobs(company_id: str, offset: int = 0, retries: int = 3) -> dict:
    url = f"https://api.smartrecruiters.com/v1/companies/{company_id}/postings"
    params = {"limit": PAGE_LIMIT, "offset": offset}
    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(url, params=params, timeout=20, headers={"User-Agent": "JobNRideBot/2.0"})
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code in [404, 400, 403]:
                return {}
            print(f"  ⚠ SmartRecruiters {company_id}: HTTP {resp.status_code}")
            return {}
        except requests.exceptions.RequestException as e:
            wait = 2 ** attempt
            print(f"  ⚠ SmartRecruiters {company_id} error (attempt {attempt}): {e}. Retry in {wait}s...")
            time.sleep(wait)
    return {}


def parse_job(raw: dict, company_name: str, company_id: str) -> dict:
    title = raw.get("name", "").strip()
    job_id = raw.get("id", "")
    apply_link = f"https://jobs.smartrecruiters.com/{company_id}/{job_id}" if job_id else ""

    location_data = raw.get("location", {}) or {}
    city = location_data.get("city", "")
    country = location_data.get("country", "")
    remote = location_data.get("remote", False)
    location_parts = [p for p in [city, country] if p]
    location = normalize_location(", ".join(location_parts))
    if remote:
        location = f"{location} (Remote)" if location and location != "Not Specified" else "Remote"

    job_type_raw = raw.get("typeOfEmployment", {})
    if isinstance(job_type_raw, dict):
        job_type_raw = job_type_raw.get("label", "")

    department = raw.get("department", {})
    if isinstance(department, dict):
        department = department.get("label", "")

    description_text = ""

    job_for = classify_job_for(title, description_text)

    return {
        "title": title,
        "company": company_name,
        "location": location or "India",
        "experience": "0-2 years" if job_for in ["intern", "fresher"] else "Not Specified",
        "jobType": normalize_job_type(str(job_type_raw)),
        "salary": "Not Disclosed",
        "description": "No description available.",
        "requirements": "Not Specified",
        "preferredSkills": "Not Specified",
        "responsibilities": "Not Specified",
        "applyLink": apply_link,
        "featuredImage": "",
        "source": f"smartrecruiters/{company_name.lower().replace(' ', '_')}",
        "jobFor": job_for,
        "country": country or "India",
        "category": str(department),
        "rawPostedDate": raw.get("releasedDate") or raw.get("updatedOn") or raw.get("createdon") or "",
    }


def scrape() -> list:
    all_jobs = []
    print(f"\n🎯 SmartRecruiters India: Scraping {len(COMPANIES)} companies...")
    for company_name, company_id in COMPANIES:
        try:
            company_jobs = []
            offset = 0
            while True:
                data = fetch_jobs(company_id, offset)
                raw_jobs = data.get("content", [])
                if not raw_jobs:
                    break
                for raw in raw_jobs:
                    try:
                        job = parse_job(raw, company_name, company_id)
                        if job["title"] and job["applyLink"]:
                            company_jobs.append(job)
                    except Exception as e:
                        print(f"    ⚠ Parse error: {e}")
                total = data.get("totalFound", 0)
                offset += PAGE_LIMIT
                if offset >= total:
                    break
                time.sleep(0.3)
            if company_jobs:
                print(f"  ✓ {company_name}: {len(company_jobs)} jobs")
                all_jobs.extend(company_jobs)
            time.sleep(0.5)
        except Exception as e:
            print(f"  ⚠ {company_name} failed: {e}")
    print(f"  → SmartRecruiters total: {len(all_jobs)} jobs")
    return all_jobs
