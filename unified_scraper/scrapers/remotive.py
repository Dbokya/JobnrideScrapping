"""
Remotive.com public API scraper.
No API key required. Remote jobs globally.
API: https://remotive.com/api/remote-jobs
"""
import requests
import time
from normalizer import (
    normalize_job_type, classify_job_for,
    clean_html, normalize_salary, normalize_skills,
    normalize_work_mode, extract_education, infer_functional_area, infer_industry,
)

SOURCE = "remotive"
API_URL = "https://remotive.com/api/remote-jobs"

# Categories to fetch
CATEGORIES = [
    "software-dev", "devops", "product", "design",
    "data", "qa", "backend", "frontend", "fullstack",
    "mobile", "customer-support", "marketing", "sales",
]


def fetch_jobs(category: str = None, retries: int = 3) -> list:
    params = {"limit": 200}
    if category:
        params["category"] = category
    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(API_URL, params=params, timeout=20, headers={"User-Agent": "JobNRideBot/2.0"})
            if resp.status_code == 200:
                return resp.json().get("jobs", [])
            print(f"  ⚠ Remotive HTTP {resp.status_code}")
            return []
        except requests.exceptions.RequestException as e:
            wait = 2 ** attempt
            print(f"  ⚠ Remotive network error (attempt {attempt}): {e}. Retry in {wait}s...")
            time.sleep(wait)
    return []


def parse_job(raw: dict) -> dict:
    title = raw.get("title", "").strip()
    company = raw.get("company_name", "").strip()
    location = raw.get("candidate_required_location", "Worldwide") or "Worldwide"
    job_type_raw = raw.get("job_type", "")
    salary_raw = raw.get("salary", "")
    description_html = raw.get("description", "")
    description_text = clean_html(description_html)
    apply_link = raw.get("url", "")
    tags = raw.get("tags", []) or []
    category = raw.get("category", "")
    logo = raw.get("company_logo", "")

    job_for = classify_job_for(title, description_text)

    job_type = normalize_job_type(job_type_raw) if job_type_raw else "Remote"
    loc_str = f"{location} (Remote)"
    
    # Extract skills from tags or description
    skills_str = normalize_skills(tags) if tags else extract_skills_from_text(description_text)

    return {
        "title": title,
        "company": company,
        "location": loc_str,
        "experience": "0-2 years" if job_for in ["intern", "fresher"] else "Not Specified",
        "jobType": job_type,
        "salary": normalize_salary(salary_raw),
        "description": description_text[:5000] if description_text else "No description available.",
        "requirements": "Not Specified",
        "preferredSkills": skills_str,
        "responsibilities": "Not Specified",
        "applyLink": apply_link,
        "featuredImage": logo or "",
        "companyLogo": logo or "",
        "source": "remotive",
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
        "aboutCompany": "",
        "notificationTitle": f"Remote Job at {company}",
        "rawPostedDate": raw.get("publication_date") or raw.get("created_at") or "",
    }


def scrape() -> list:
    all_jobs = []
    seen_ids = set()
    print(f"\n🌐 Remotive: Fetching remote jobs...")
    raw_jobs = fetch_jobs()  # fetch all at once
    for raw in raw_jobs:
        try:
            jid = raw.get("id")
            if jid in seen_ids:
                continue
            seen_ids.add(jid)
            job = parse_job(raw)
            if job["title"] and job["company"] and job["applyLink"]:
                all_jobs.append(job)
        except Exception as e:
            print(f"  ⚠ Remotive parse error: {e}")
    print(f"  → Remotive total: {len(all_jobs)} jobs")
    return all_jobs
