"""
Himalayas.app public API scraper.
No API key required. Remote-first jobs.
API: https://himalayas.app/jobs/api
"""
import requests
import time
from normalizer import (
    normalize_job_type, classify_job_for,
    clean_html, normalize_salary, normalize_skills,
    normalize_work_mode, extract_education, infer_functional_area, infer_industry,
)

SOURCE = "himalayas"
API_URL = "https://himalayas.app/jobs/api"
MAX_PAGES = 5
PAGE_SIZE = 100


def fetch_page(page: int, retries: int = 3) -> dict:
    params = {"limit": PAGE_SIZE, "offset": (page - 1) * PAGE_SIZE}
    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(API_URL, params=params, timeout=20, headers={"User-Agent": "JobNRideBot/2.0"})
            if resp.status_code == 200:
                return resp.json()
            return {}
        except requests.exceptions.RequestException as e:
            wait = 2 ** attempt
            print(f"  ⚠ Himalayas error (attempt {attempt}): {e}. Retry in {wait}s...")
            time.sleep(wait)
    return {}


def parse_job(raw: dict) -> dict:
    title = raw.get("title", "").strip()
    company_data = raw.get("company", {}) or {}
    company = company_data.get("name", "") or raw.get("companyName", "")

    locations = raw.get("locationRestrictions", []) or []
    location_str = ", ".join(locations) if locations else "Worldwide"
    location = f"{location_str} (Remote)"

    job_type_raw = raw.get("jobType", "")
    salary_min = raw.get("salaryMin")
    salary_max = raw.get("salaryMax")
    currency = raw.get("salaryCurrency", "USD")

    if salary_min and salary_max:
        salary = f"{currency} {salary_min:,} - {salary_max:,}"
    elif salary_min:
        salary = f"{currency} {salary_min:,}+"
    else:
        salary = "Not Disclosed"

    description_html = raw.get("descriptionHtml", "") or raw.get("description", "")
    description_text = clean_html(description_html)
    apply_link = raw.get("applicationUrl", "") or raw.get("url", "")
    skills = raw.get("skills", []) or []
    logo = company_data.get("logoUrl", "")
    category = raw.get("department", "") or raw.get("category", "")

    job_for = classify_job_for(title, description_text)

    job_type = normalize_job_type(job_type_raw) if job_type_raw else "Remote"
    skills_str = normalize_skills(skills)
    about_company = company_data.get("description", "") or company_data.get("about", "")

    return {
        "title": title,
        "company": company,
        "location": location,
        "experience": "0-2 years" if job_for in ["intern", "fresher"] else "Not Specified",
        "jobType": job_type,
        "salary": salary,
        "description": description_text[:5000] if description_text else "No description available.",
        "requirements": "Not Specified",
        "preferredSkills": skills_str,
        "responsibilities": "Not Specified",
        "applyLink": apply_link,
        "featuredImage": logo or "",
        "companyLogo": logo or "",
        "source": "himalayas",
        "jobFor": job_for,
        "country": "Remote",
        "category": category,
        "workMode": "Remote",
        "functionalArea": infer_functional_area(title, category, description_text),
        "industry": infer_industry(company, category, title),
        "educationRequirement": extract_education(description_text),
        "noticePeriod": "Not Specified",
        "totalOpenings": "Not Specified",
        "benefits": "",
        "aboutCompany": clean_html(about_company)[:500] if about_company else "",
        "notificationTitle": f"Remote Job at {company}",
        "rawPostedDate": raw.get("createdAt") or raw.get("publishedAt") or raw.get("postedAt") or "",
    }


def scrape() -> list:
    all_jobs = []
    print(f"\n🏔️  Himalayas: Fetching remote jobs...")
    for page in range(1, MAX_PAGES + 1):
        data = fetch_page(page)
        raw_jobs = data.get("jobs", [])
        if not raw_jobs:
            break
        print(f"  ✓ Page {page}: {len(raw_jobs)} jobs")
        for raw in raw_jobs:
            try:
                job = parse_job(raw)
                if job["title"] and job["company"] and job["applyLink"]:
                    all_jobs.append(job)
            except Exception as e:
                print(f"  ⚠ Himalayas parse error: {e}")
        time.sleep(0.5)
    print(f"  → Himalayas total: {len(all_jobs)} jobs")
    return all_jobs
