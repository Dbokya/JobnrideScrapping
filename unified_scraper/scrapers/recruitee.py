"""
Recruitee ATS public API scraper.
No API key required. Used by several India-presence IT firms.
API: https://{company}.recruitee.com/api/offers/
"""
import requests
import time
from normalizer import (
    normalize_job_type, classify_job_for,
    clean_html, normalize_location, normalize_salary, build_description,
    normalize_work_mode, extract_education, infer_functional_area, infer_industry,
    extract_skills_from_text,
)

SOURCE = "recruitee"

# Format: (display_name, company_slug)  — verified via discover_ats.py
COMPANIES = [
    ("Synechron",          "synechron"),
    ("Publicis Sapient",   "publicissapient"),
    ("Ramco Systems",      "ramco"),
    ("Navi",               "navi"),
]


def fetch_jobs(company_slug: str, retries: int = 3) -> list:
    url = f"https://{company_slug}.recruitee.com/api/offers/"
    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(url, timeout=15, headers={"User-Agent": "JobNRideBot/2.0"})
            if resp.status_code == 200:
                return resp.json().get("offers", [])
            if resp.status_code in (404, 400, 403):
                return []
            print(f"  ⚠ Recruitee {company_slug}: HTTP {resp.status_code}")
            return []
        except requests.exceptions.RequestException as e:
            wait = 2 ** attempt
            print(f"  ⚠ Network error for {company_slug} (attempt {attempt}): {e}. Retrying in {wait}s...")
            time.sleep(wait)
    return []


def parse_job(raw: dict, company_name: str, company_slug: str) -> dict:
    title = (raw.get("title") or "").strip()
    apply_link = raw.get("careers_url") or raw.get("careers_apply_url") or ""

    location = normalize_location(
        raw.get("location") or ", ".join(p for p in [raw.get("city"), raw.get("country")] if p)
    )
    country = raw.get("country") or ""
    if raw.get("remote"):
        location = f"{location} (Remote)" if location and location != "Not Specified" else "Remote"

    department = raw.get("department") or ""
    job_type_raw = raw.get("employment_type_code") or raw.get("employment_type") or ""

    raw_description_html = raw.get("description") or ""
    description_text = clean_html(raw_description_html)
    requirements_text = clean_html(raw.get("requirements") or "")

    job_for = classify_job_for(title, description_text)
    job_type = normalize_job_type(str(job_type_raw))

    # Recruitee `salary` may be a dict {min,max,currency} or a string
    salary_raw = raw.get("salary")
    if isinstance(salary_raw, dict):
        lo, hi = salary_raw.get("min"), salary_raw.get("max")
        salary_raw = f"{lo} - {hi}" if (lo or hi) else ""
    salary_raw = salary_raw or ""

    skills_text = extract_skills_from_text(f"{description_text} {requirements_text}")
    full_description = build_description(
        raw=description_text,
        responsibilities="",
        requirements=requirements_text,
        skills=skills_text,
        job_type=job_type,
        location=location or "India",
    )

    work_mode = "Remote" if raw.get("remote") else (
        "Hybrid" if raw.get("hybrid") else normalize_work_mode(location, job_type)
    )

    return {
        "title": title,
        "company": raw.get("company_name") or company_name,
        "location": location or "Not Specified",
        "experience": "0-2 years" if job_for in ["intern", "fresher"] else "Not Specified",
        "jobType": job_type,
        "salary": normalize_salary(salary_raw),
        "description": full_description,
        "rawDescriptionHtml": raw_description_html,
        "requirements": requirements_text[:1000] if requirements_text else "Not Specified",
        "preferredSkills": skills_text or "Not Specified",
        "responsibilities": "Not Specified",
        "applyLink": apply_link,
        "featuredImage": raw.get("cover_image") or "",
        "source": f"recruitee/{company_slug}",
        "jobFor": job_for,
        "country": country,
        "category": department,
        "workMode": work_mode,
        "functionalArea": infer_functional_area(title, department, description_text),
        "industry": infer_industry(company_name, department, title),
        "educationRequirement": extract_education(requirements_text + " " + description_text),
        "noticePeriod": "Not Specified",
        "totalOpenings": "Not Specified",
        "benefits": "",
        "aboutCompany": "",
        "notificationTitle": f"New Job at {company_name}",
        "rawPostedDate": raw.get("published_at") or raw.get("created_at") or "",
    }


def scrape() -> list:
    all_jobs = []
    print(f"\n🟣 Recruitee: Scraping {len(COMPANIES)} companies...")
    for company_name, company_slug in COMPANIES:
        raw_jobs = fetch_jobs(company_slug)
        if not raw_jobs:
            continue
        company_jobs = []
        for raw in raw_jobs:
            try:
                job = parse_job(raw, company_name, company_slug)
                if job["title"] and job["applyLink"]:
                    company_jobs.append(job)
            except Exception as e:
                print(f"  ⚠ Parse error for {company_slug}: {e}")
        if company_jobs:
            print(f"  ✓ {company_name}: {len(company_jobs)} jobs")
            all_jobs.extend(company_jobs)
        time.sleep(0.3)
    print(f"  → Recruitee total: {len(all_jobs)} jobs")
    return all_jobs
