"""
Freshteam (Freshworks Recruiting) public API scraper.
No API key required for public job listings.
API: https://{subdomain}.freshteam.com/api/job_postings?status=published
Many Indian startups and mid-size companies use Freshteam.
"""
import requests
import time
from normalizer import (
    normalize_job_type, classify_job_for,
    clean_html, normalize_location, build_description,
    normalize_work_mode, extract_education, infer_functional_area, infer_industry,
)

SOURCE = "freshteam"

# Format: (display_name, subdomain)
COMPANIES = [
    # IT Services
    ("Freshworks",          "freshworks"),
    ("Zoho",                "zoho"),
    ("Tata Communications", "tatacommunications"),
    ("WNS Global",          "wns"),
    ("Mphasis",             "mphasis"),
    ("Zensar",              "zensar"),
    ("KPIT",                "kpit"),
    # Indian Startups
    ("Razorpay",            "razorpay"),
    ("BrowserStack",        "browserstack"),
    ("Postman",             "postman"),
    ("Chargebee",           "chargebee"),
    ("Clevertap",           "clevertap"),
    ("MoEngage",            "moengage"),
    ("LeadSquared",         "leadsquared"),
    ("Darwinbox",           "darwinbox"),
    ("Hasura",              "hasura"),
    ("Smallcase",           "smallcase"),
    ("Jupiter Money",       "jupitermoney"),
    ("Niyo",                "niyo"),
    ("Slice",               "sliceit"),
    ("Fi Money",            "fimoney"),
    ("Groww",               "groww"),
    ("Upstox",              "upstox"),
    ("5paisa",              "fivepaisa"),
    ("Navi",                "navi"),
    ("KreditBee",           "kreditbee"),
    ("MoneyTap",            "moneytap"),
    ("Lendingkart",         "lendingkart"),
    ("Capital Float",       "capitalfloat"),
    ("Cashfree",            "cashfree"),
    ("Setu",                "setu"),
    # Edtech
    ("Byju's",              "byjus"),
    ("Unacademy",           "unacademy"),
    ("Vedantu",             "vedantu"),
    ("upGrad",              "upgrad"),
    ("Simplilearn",         "simplilearn"),
    ("Scaler",              "scaler"),
    ("InterviewBit",        "interviewbit"),
    # Healthtech
    ("Practo",              "practo"),
    ("PharmEasy",           "pharmeasy"),
    ("1mg",                 "1mg"),
    ("Healthifyme",         "healthifyme"),
    # Logistics / Other
    ("Delhivery",           "delhivery"),
    ("Shiprocket",          "shiprocket"),
    ("Ecom Express",        "ecomexpress"),
    ("Porter",              "porter"),
    ("Shadowfax",           "shadowfax"),
]


def fetch_jobs(subdomain: str, retries: int = 3) -> list:
    url = f"https://{subdomain}.freshteam.com/api/job_postings"
    params = {"status": "published"}
    headers = {
        "User-Agent": "JobNRideBot/2.0",
        "Accept": "application/json",
    }
    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(url, params=params, headers=headers, timeout=20)
            if resp.status_code == 200:
                return resp.json() if isinstance(resp.json(), list) else resp.json().get("job_postings", [])
            if resp.status_code in [404, 400, 403, 301, 302]:
                return []
            print(f"  ⚠ Freshteam {subdomain}: HTTP {resp.status_code}")
            return []
        except requests.exceptions.RequestException as e:
            wait = 2 ** attempt
            print(f"  ⚠ Freshteam {subdomain} error (attempt {attempt}): {e}. Retry in {wait}s...")
            time.sleep(wait)
    return []


def parse_job(raw: dict, company_name: str, subdomain: str) -> dict:
    title = raw.get("title", "").strip()
    job_id = raw.get("id", "")
    apply_link = raw.get("url", "") or f"https://{subdomain}.freshteam.com/jobs/{job_id}/detail" if job_id else ""

    city = raw.get("city", "") or ""
    state = raw.get("state", "") or ""
    country = raw.get("country", "") or "India"
    location_parts = [p for p in [city, state] if p]
    location = normalize_location(", ".join(location_parts) if location_parts else country)

    remote = raw.get("remote", False)
    if remote:
        location = f"{location} (Remote)" if location and location != "Not Specified" else "Remote"

    job_type_raw = raw.get("job_type", "") or ""
    description_html = raw.get("description", "") or ""
    description_text = clean_html(description_html)
    requirements_html = raw.get("qualifications", "") or ""
    requirements_text = clean_html(requirements_html)
    responsibilities_html = raw.get("responsibilities", "") or ""
    responsibilities_text = clean_html(responsibilities_html)

    department = raw.get("department", {})
    if isinstance(department, dict):
        department = department.get("name", "")

    exp_min = raw.get("exp_min")
    exp_max = raw.get("exp_max")
    if exp_min is not None and exp_max is not None:
        exp_raw = f"{exp_min}-{exp_max} years"
    elif exp_min is not None:
        exp_raw = f"{exp_min}+ years"
    else:
        exp_raw = ""

    from normalizer import normalize_experience
    experience = normalize_experience(exp_raw) if exp_raw else "Not Specified"

    job_for = classify_job_for(title, description_text)
    job_type = normalize_job_type(str(job_type_raw))
    loc_str = location or "India"

    full_description = build_description(
        raw=description_text,
        responsibilities=responsibilities_text,
        requirements=requirements_text,
        job_type=job_type,
        location=loc_str,
    )

    dept_str = str(department)
    
    # Extract skills from description, requirements, and department
    skills_text = extract_skills_from_text(full_description)
    if not skills_text or skills_text == "Not Specified":
        skills_text = extract_skills_from_text(f"{requirements_text} {dept_str}")
    
    return {
        "title": title,
        "company": company_name,
        "location": loc_str,
        "experience": experience,
        "jobType": job_type,
        "salary": "Not Disclosed",
        "description": full_description,
        "rawDescriptionHtml": description_html,
        "requirements": requirements_text[:1000] if requirements_text else "Not Specified",
        "preferredSkills": skills_text,
        "responsibilities": responsibilities_text[:1000] if responsibilities_text else "Not Specified",
        "applyLink": apply_link,
        "featuredImage": "",
        "source": f"freshteam/{subdomain}",
        "jobFor": job_for,
        "country": "India",
        "category": dept_str,
        "workMode": normalize_work_mode(loc_str, job_type),
        "functionalArea": infer_functional_area(title, dept_str, description_text),
        "industry": infer_industry(company_name, dept_str, title),
        "educationRequirement": extract_education(requirements_text + " " + description_text),
        "noticePeriod": "Not Specified",
        "totalOpenings": "Not Specified",
        "benefits": "",
        "aboutCompany": "",
        "notificationTitle": f"New Job at {company_name}",
        "rawPostedDate": raw.get("updated_at") or raw.get("created_at") or "",
    }


def scrape() -> list:
    all_jobs = []
    print(f"\n🌸 Freshteam India: Scraping {len(COMPANIES)} companies...")
    for company_name, subdomain in COMPANIES:
        try:
            raw_jobs = fetch_jobs(subdomain)
            if not raw_jobs:
                continue
            company_jobs = []
            for raw in raw_jobs:
                try:
                    job = parse_job(raw, company_name, subdomain)
                    if job["title"] and job["applyLink"]:
                        company_jobs.append(job)
                except Exception as e:
                    print(f"    ⚠ Parse error: {e}")
            if company_jobs:
                print(f"  ✓ {company_name}: {len(company_jobs)} jobs")
                all_jobs.extend(company_jobs)
            time.sleep(0.4)
        except Exception as e:
            print(f"  ⚠ {company_name} failed: {e}")
    print(f"  → Freshteam total: {len(all_jobs)} jobs")
    return all_jobs
