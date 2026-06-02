"""
Remote OK public API scraper.
No API key required. Any company, fully remote jobs worldwide.
API: https://remoteok.com/api  (returns JSON array, first element is metadata)
"""
import requests
import time
from normalizer import (
    normalize_job_type, classify_job_for,
    clean_html, normalize_skills,
    normalize_work_mode, extract_education, infer_functional_area, infer_industry,
)

SOURCE = "remoteok"
API_URL = "https://remoteok.com/api"

# IT-relevant tags to filter jobs (Remote OK returns all categories)
IT_TAGS = {
    "dev", "developer", "engineer", "engineering", "software", "backend",
    "frontend", "fullstack", "full-stack", "mobile", "android", "ios",
    "devops", "sre", "cloud", "aws", "gcp", "azure", "infra",
    "data", "ml", "ai", "machine-learning", "python", "javascript",
    "typescript", "react", "node", "java", "golang", "rust", "scala",
    "php", "ruby", "kotlin", "swift", "flutter", "web", "api",
    "database", "dba", "sql", "nosql", "product", "design", "ux", "ui",
    "qa", "testing", "security", "blockchain", "web3",
}


def fetch_jobs(retries: int = 3) -> list:
    headers = {
        "User-Agent": "JobNRideBot/2.0",
        "Accept": "application/json",
    }
    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(API_URL, headers=headers, timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                # First element is metadata object, rest are jobs
                return [j for j in data if isinstance(j, dict) and j.get("id")]
            print(f"  ⚠ RemoteOK HTTP {resp.status_code}")
            return []
        except requests.exceptions.RequestException as e:
            wait = 2 ** attempt
            print(f"  ⚠ RemoteOK error (attempt {attempt}): {e}. Retry in {wait}s...")
            time.sleep(wait)
    return []


def _is_it_job(tags: list) -> bool:
    """Return True if any tag suggests an IT/tech role."""
    for tag in tags:
        tl = tag.lower().replace(" ", "-")
        if any(it in tl for it in IT_TAGS):
            return True
    return False


def parse_job(raw: dict) -> dict:
    title = raw.get("position", "").strip()
    company = raw.get("company", "").strip()
    description_html = raw.get("description", "") or ""
    description_text = clean_html(description_html)
    apply_link = raw.get("url", "") or raw.get("apply_url", "")
    tags = raw.get("tags", []) or []
    salary_min = raw.get("salary_min")
    salary_max = raw.get("salary_max")
    logo = raw.get("company_logo", "")

    if salary_min and salary_max:
        salary = f"${salary_min:,} - ${salary_max:,}"
    elif salary_min:
        salary = f"${salary_min:,}+"
    else:
        salary = "Not Disclosed"

    location_raw = raw.get("location", "") or "Worldwide"
    # RemoteOK jobs are always remote
    location = f"{location_raw} (Remote)" if "remote" not in location_raw.lower() else location_raw

    skills_str = normalize_skills(tags)
    job_for = classify_job_for(title, description_text)

    return {
        "title": title,
        "company": company or "Not Specified",
        "location": location,
        "experience": "0-2 years" if job_for in ["intern", "fresher"] else "Not Specified",
        "jobType": "Remote",
        "salary": salary,
        "description": description_text[:5000] if description_text else "No description available.",
        "requirements": "Not Specified",
        "preferredSkills": skills_str,
        "responsibilities": "Not Specified",
        "applyLink": apply_link,
        "featuredImage": logo or "",
        "companyLogo": logo or "",
        "source": "remoteok",
        "jobFor": job_for,
        "country": "Remote",
        "category": tags[0] if tags else "",
        "workMode": "Remote",
        "functionalArea": infer_functional_area(title, tags[0] if tags else "", description_text),
        "industry": infer_industry(company, tags[0] if tags else "", title),
        "educationRequirement": extract_education(description_text),
        "noticePeriod": "Not Specified",
        "totalOpenings": "Not Specified",
        "benefits": "",
        "aboutCompany": "",
        "notificationTitle": f"Remote Job at {company}" if company else "Remote IT Job",
        "rawPostedDate": raw.get("date") or raw.get("epoch") or "",
    }


def scrape() -> list:
    all_jobs = []
    print(f"\n🌐 RemoteOK: Fetching any-company remote jobs...")
    raw_jobs = fetch_jobs()
    if not raw_jobs:
        print("  ⚠ RemoteOK: No jobs returned")
        return []

    it_count = 0
    skip_count = 0
    for raw in raw_jobs:
        try:
            tags = raw.get("tags", []) or []
            if not _is_it_job(tags):
                skip_count += 1
                continue
            job = parse_job(raw)
            if job["title"] and job["company"] != "Not Specified" and job["applyLink"]:
                all_jobs.append(job)
                it_count += 1
        except Exception as e:
            print(f"  ⚠ RemoteOK parse error: {e}")

    print(f"  → RemoteOK: {it_count} IT remote jobs (skipped {skip_count} non-IT)")
    return all_jobs
