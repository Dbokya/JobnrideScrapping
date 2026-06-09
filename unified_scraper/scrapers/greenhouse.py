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
    build_description, normalize_work_mode, extract_education,
    infer_functional_area, infer_industry, extract_skills_from_text,
)

SOURCE = "greenhouse"

# Company slugs — verified live via audit_slugs.py
COMPANIES = [
    "tcs",
    "phonepe",
    "postman",
    "pubmatic",
    "inmobi",
    "groww",
    "slice",
    "druva",
    "stripe",
    "figma",
    "airbnb",
    "reddit",
    "discord",
    "duolingo",
    "robinhood",
    "brex",
    "databricks",
    "mongodb",
    "elastic",
    "twilio",
    "intercom",
    "datadog",
    "pagerduty",
    "cloudflare",
    "fastly",
    "netlify",
    "mixpanel",
    "amplitude",
    "contentful",
    "algolia",
    "okta",
    "launchdarkly",
    "airtable",
    "webflow",
    "make",
    "remote",
    "gusto",
    "lattice",
    "greenhouse",
    "affirm",
    "chime",
    "faire",
    "sigmoid",
    "highradius",
    "thoughtworks",
    "vercel",
    "planetscale",
    "watershed",
    "cerebral",
    "turing",
    "iris",
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
    # Keep raw HTML so ai_parser can extract structured sections from it
    raw_description_html = content_html

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

    job_type = normalize_job_type(job_type_raw) if job_type_raw else (
        "Internship" if job_for == "intern" else "Full-Time"
    )
    dept = departments[0].get("name", "") if departments else ""

    # Extract skills from description and metadata
    skills_text = extract_skills_from_text(description_text) or extract_skills_from_text(str(metadata))

    return {
        "title": title,
        "company": company_name,
        "location": location,
        "experience": experience,
        "jobType": job_type,
        "salary": normalize_salary(salary_raw),
        "description": description_text[:5000] if description_text else "No description available.",
        "rawDescriptionHtml": raw_description_html,
        "requirements": "Not Specified",
        "preferredSkills": skills_text,
        "responsibilities": "Not Specified",
        "applyLink": apply_link,
        "featuredImage": "",
        "source": f"greenhouse/{company_slug}",
        "jobFor": job_for,
        "country": "",
        "category": dept,
        "workMode": normalize_work_mode(location, job_type),
        "functionalArea": infer_functional_area(title, dept, description_text),
        "industry": infer_industry(company_name, dept, title),
        "educationRequirement": extract_education(description_text),
        "noticePeriod": "Not Specified",
        "totalOpenings": "Not Specified",
        "benefits": "",
        "aboutCompany": "",
        "notificationTitle": f"New Job at {company_name}",
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
