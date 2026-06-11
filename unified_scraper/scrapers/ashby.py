"""
Ashby ATS public API scraper.
No API key required. Used by many modern startups.
API: https://api.ashbyhq.com/posting-api/job-board/{company}
"""
import requests
import time
from normalizer import (
    normalize_experience, normalize_job_type, classify_job_for,
    clean_html, normalize_location, normalize_skills,
    normalize_work_mode, extract_education, infer_functional_area, infer_industry,
    extract_skills_from_text,
)

SOURCE = "ashby"

# Company slugs — verified live via audit_slugs.py
COMPANIES = [
    "linear",
    "supabase",
    "cursor",
    "perplexity",
    "openai",
    "cohere",
    "replit",
    "railway",
    "neon",
    "resend",
    "sarvam",
    "clarisights",
    "signoz",
    "notion",
    "merge",
    "finch",
    "stackone",
    "ramp",
    "watershed",
    "read-ai",
    "deel",
    "inngest",
]


def fetch_jobs(company_slug: str, retries: int = 3) -> list:
    url = f"https://api.ashbyhq.com/posting-api/job-board/{company_slug}"
    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(url, timeout=15, headers={"User-Agent": "JobNRideBot/2.0"})
            if resp.status_code == 200:
                data = resp.json()
                # Ashby returns {"jobs": [...]}; older API used "jobPostings"
                return data.get("jobs", data.get("jobPostings", []))
            if resp.status_code in [404, 400]:
                return []
            print(f"  ⚠ Ashby {company_slug}: HTTP {resp.status_code}")
            return []
        except requests.exceptions.RequestException as e:
            wait = 2 ** attempt
            print(f"  ⚠ Network error for {company_slug} (attempt {attempt}): {e}. Retry in {wait}s...")
            time.sleep(wait)
    return []


def parse_job(raw: dict, company_slug: str) -> dict:
    title = raw.get("title", "").strip()
    apply_link = raw.get("jobUrl", "") or raw.get("applyUrl", "")

    location_name = ""
    loc_data = raw.get("location", {})
    if isinstance(loc_data, dict):
        location_name = loc_data.get("name", "") or loc_data.get("locationStr", "")
    elif isinstance(loc_data, str):
        location_name = loc_data

    # Also check locationStr at root
    location_name = location_name or raw.get("locationStr", "")
    location = normalize_location(location_name)

    employment_type = raw.get("employmentType", "")
    description_html = raw.get("descriptionHtml", "") or raw.get("description", "")
    description_text = clean_html(description_html)

    department = raw.get("department", "") or ""
    team = raw.get("team", "") or ""

    company_name = raw.get("organizationName", "") or company_slug.replace("-", " ").title()
    job_for = classify_job_for(title, description_text)

    job_type = normalize_job_type(employment_type)
    loc_str = location or "Not Specified"
    dept = department or team
    
    # Extract skills from description
    skills_text = extract_skills_from_text(description_text)
    if not skills_text or skills_text == "Not Specified":
        skills_text = extract_skills_from_text(dept)

    return {
        "title": title,
        "company": company_name,
        "location": loc_str,
        "experience": "0-2 years" if job_for in ["intern", "fresher"] else "Not Specified",
        "jobType": job_type,
        "salary": "Not Disclosed",
        "description": description_text[:5000] if description_text else "No description available.",
        "rawDescriptionHtml": description_html,
        "requirements": "Not Specified",
        "preferredSkills": skills_text,
        "responsibilities": "Not Specified",
        "applyLink": apply_link,
        "featuredImage": "",
        "source": f"ashby/{company_slug}",
        "jobFor": job_for,
        "country": "",
        "category": dept,
        "workMode": normalize_work_mode(loc_str, employment_type),
        "functionalArea": infer_functional_area(title, dept, description_text),
        "industry": infer_industry(company_name, dept, title),
        "educationRequirement": extract_education(description_text),
        "noticePeriod": "Not Specified",
        "totalOpenings": "Not Specified",
        "benefits": "",
        "aboutCompany": "",
        "notificationTitle": f"New Job at {company_name}",
        "rawPostedDate": raw.get("publishedAt") or raw.get("publishedDate") or raw.get("updatedAt") or raw.get("createdAt") or "",
    }


def scrape() -> list:
    all_jobs = []
    print(f"\n🔷 Ashby: Scraping {len(COMPANIES)} companies...")
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
    print(f"  → Ashby total: {len(all_jobs)} jobs")
    return all_jobs
