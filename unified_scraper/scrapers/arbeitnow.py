"""
Arbeitnow public API scraper.
No API key required. EU + Remote jobs.
API: https://www.arbeitnow.com/api/job-board-api
"""
import requests
import time
from normalizer import (
    normalize_job_type, classify_job_for,
    clean_html, normalize_location, normalize_skills,
    normalize_work_mode, extract_education, infer_functional_area, infer_industry,
    extract_skills_from_text,
)

SOURCE = "arbeitnow"
API_URL = "https://www.arbeitnow.com/api/job-board-api"
MAX_PAGES = 5


def fetch_page(page: int, retries: int = 3) -> list:
    params = {"page": page}
    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(API_URL, params=params, timeout=20, headers={"User-Agent": "JobNRideBot/2.0"})
            if resp.status_code == 200:
                data = resp.json()
                return data.get("data", [])
            return []
        except requests.exceptions.RequestException as e:
            wait = 2 ** attempt
            print(f"  ⚠ Arbeitnow error (attempt {attempt}): {e}. Retry in {wait}s...")
            time.sleep(wait)
    return []


def parse_job(raw: dict) -> dict:
    title = raw.get("title", "").strip()
    company = raw.get("company_name", "").strip()
    location = normalize_location(raw.get("location", ""))
    remote = raw.get("remote", False)
    job_types = raw.get("job_types", []) or []
    job_type_raw = job_types[0] if job_types else ""
    description_html = raw.get("description", "")
    description_text = clean_html(description_html)
    apply_link = raw.get("url", "")
    tags = raw.get("tags", []) or []
    slug = raw.get("slug", "")

    if remote and "remote" not in location.lower():
        location = f"{location} (Remote)" if location and location != "Not Specified" else "Remote"

    job_for = classify_job_for(title, description_text)

    job_type = normalize_job_type(job_type_raw)
    loc_str = location or "Remote"
    skills_str = normalize_skills(tags) if tags else extract_skills_from_text(description_text)

    return {
        "title": title,
        "company": company,
        "location": loc_str,
        "experience": "0-2 years" if job_for in ["intern", "fresher"] else "Not Specified",
        "jobType": job_type,
        "salary": "Not Disclosed",
        "description": description_text[:5000] if description_text else "No description available.",
        "rawDescriptionHtml": description_html,
        "requirements": "Not Specified",
        "preferredSkills": skills_str,
        "responsibilities": "Not Specified",
        "applyLink": apply_link,
        "featuredImage": "",
        "source": "arbeitnow",
        "jobFor": job_for,
        "country": "Remote",
        "category": "",
        "workMode": "Remote",
        "functionalArea": infer_functional_area(title, "", description_text),
        "industry": infer_industry(company, "", title),
        "educationRequirement": extract_education(description_text),
        "noticePeriod": "Not Specified",
        "totalOpenings": "Not Specified",
        "benefits": "",
        "aboutCompany": "",
        "notificationTitle": f"Remote Job at {company}",
        "rawPostedDate": raw.get("created_at") or raw.get("date_posted") or "",
    }


def scrape() -> list:
    all_jobs = []
    print(f"\n🌐 Arbeitnow: Fetching Remote jobs (remote=True only)...")
    for page in range(1, MAX_PAGES + 1):
        raw_jobs = fetch_page(page)
        if not raw_jobs:
            break
        print(f"  ✓ Page {page}: {len(raw_jobs)} jobs")
        for raw in raw_jobs:
            try:
                # Only include remote jobs — skip EU on-site roles
                if not raw.get("remote", False):
                    continue
                job = parse_job(raw)
                if job["title"] and job["company"] and job["applyLink"]:
                    all_jobs.append(job)
            except Exception as e:
                print(f"  ⚠ Arbeitnow parse error: {e}")
        time.sleep(0.5)
    print(f"  → Arbeitnow total: {len(all_jobs)} jobs")
    return all_jobs
