"""
Wellfound (AngelList Talent) job scraper for Indian startups.
Uses the public Wellfound job search API (no key required).
Focuses on Indian IT startups.
API: https://wellfound.com/jobs/api
"""
import requests
import time
from normalizer import (
    normalize_job_type, classify_job_for,
    clean_html, normalize_location, normalize_skills,
)

SOURCE = "wellfound"

BASE_URL = "https://wellfound.com/jobs/api"

# Search queries focused on India IT
SEARCH_QUERIES = [
    {"role": "Software Engineer",        "location": "India"},
    {"role": "Backend Engineer",         "location": "India"},
    {"role": "Frontend Engineer",        "location": "India"},
    {"role": "Full Stack Engineer",      "location": "India"},
    {"role": "DevOps Engineer",          "location": "India"},
    {"role": "Data Engineer",            "location": "India"},
    {"role": "Data Scientist",           "location": "India"},
    {"role": "Machine Learning Engineer","location": "India"},
    {"role": "Product Manager",          "location": "India"},
    {"role": "Mobile Developer",         "location": "India"},
    {"role": "Android Developer",        "location": "India"},
    {"role": "iOS Developer",            "location": "India"},
    {"role": "Cloud Engineer",           "location": "India"},
    {"role": "Security Engineer",        "location": "India"},
    {"role": "SRE",                      "location": "India"},
    {"role": "QA Engineer",              "location": "India"},
    {"role": "Technical Lead",           "location": "India"},
    {"role": "Engineering Manager",      "location": "India"},
    {"role": "Software Engineer",        "location": "Bangalore"},
    {"role": "Software Engineer",        "location": "Mumbai"},
    {"role": "Software Engineer",        "location": "Hyderabad"},
    {"role": "Software Engineer",        "location": "Pune"},
    {"role": "Software Engineer",        "location": "Chennai"},
    {"role": "Software Engineer",        "location": "Delhi"},
    {"role": "Software Engineer",        "location": "Remote India"},
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; JobNRideBot/2.0)",
    "Accept": "application/json",
    "Referer": "https://wellfound.com/jobs",
    "X-Requested-With": "XMLHttpRequest",
}


def fetch_jobs(role: str, location: str, page: int = 1, retries: int = 3) -> dict:
    params = {
        "role": role,
        "location": location,
        "page": page,
    }
    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(BASE_URL, params=params, headers=HEADERS, timeout=20)
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code in [403, 404, 429]:
                if resp.status_code == 429:
                    print(f"  ⚠ Wellfound rate limited. Waiting 15s...")
                    time.sleep(15)
                    continue
                return {}
            return {}
        except requests.exceptions.RequestException as e:
            wait = 2 ** attempt
            print(f"  ⚠ Wellfound error (attempt {attempt}): {e}. Retry in {wait}s...")
            time.sleep(wait)
    return {}


def parse_job(raw: dict) -> dict:
    title = raw.get("role", "") or raw.get("title", "")
    title = title.strip()

    startup = raw.get("startup", {}) or {}
    company = startup.get("name", "") or raw.get("company", "")

    locations = raw.get("locations", []) or []
    location_names = [l.get("displayName", "") if isinstance(l, dict) else str(l) for l in locations]
    location = normalize_location(", ".join([l for l in location_names if l]))

    remote = raw.get("remote", False) or any("remote" in l.lower() for l in location_names)
    if remote and "remote" not in location.lower():
        location = f"{location} (Remote)" if location and location != "Not Specified" else "Remote"

    job_type_raw = raw.get("jobType", "") or raw.get("employment_type", "")
    salary_min = raw.get("salaryMin") or raw.get("compensation", {}).get("min") if isinstance(raw.get("compensation"), dict) else None
    salary_max = raw.get("salaryMax") or raw.get("compensation", {}).get("max") if isinstance(raw.get("compensation"), dict) else None

    if salary_min and salary_max:
        salary = f"₹{salary_min:,} - ₹{salary_max:,}"
    elif salary_min:
        salary = f"₹{salary_min:,}+"
    else:
        salary = "Not Disclosed"

    description_html = raw.get("description", "") or startup.get("productDesc", "")
    description_text = clean_html(description_html)

    skills_raw = raw.get("skills", []) or raw.get("tags", [])
    skills = normalize_skills(skills_raw)

    apply_link = raw.get("url", "") or raw.get("jobUrl", "")
    if not apply_link:
        slug = startup.get("slug", "")
        job_id = raw.get("id", "")
        if slug and job_id:
            apply_link = f"https://wellfound.com/jobs/{job_id}"

    logo = startup.get("logoUrl", "") or startup.get("thumbUrl", "")

    job_for = classify_job_for(title, description_text)

    return {
        "title": title,
        "company": company or "Not Specified",
        "location": location or "India",
        "experience": "0-2 years" if job_for in ["intern", "fresher"] else "Not Specified",
        "jobType": normalize_job_type(str(job_type_raw)) if job_type_raw else "Full-Time",
        "salary": salary,
        "description": description_text[:5000] if description_text else "No description available.",
        "requirements": "Not Specified",
        "preferredSkills": skills,
        "responsibilities": "Not Specified",
        "applyLink": apply_link,
        "featuredImage": logo or "",
        "source": "wellfound",
        "jobFor": job_for,
        "country": "India",
        "category": "",
        "rawPostedDate": raw.get("posted_at") or raw.get("createdAt") or raw.get("updated_at") or "",
    }


def scrape() -> list:
    all_jobs = []
    seen_apply_links = set()

    print(f"\n🦄 Wellfound: Fetching Indian startup jobs...")
    for query in SEARCH_QUERIES:
        role = query["role"]
        location = query["location"]
        try:
            data = fetch_jobs(role, location)
            raw_jobs = data.get("jobs", []) or data.get("jobListings", []) or []
            if not raw_jobs:
                time.sleep(1)
                continue
            for raw in raw_jobs:
                try:
                    job = parse_job(raw)
                    link = job.get("applyLink", "")
                    if link and link in seen_apply_links:
                        continue
                    if link:
                        seen_apply_links.add(link)
                    if job["title"] and job["company"] != "Not Specified":
                        all_jobs.append(job)
                except Exception as e:
                    print(f"    ⚠ Parse error: {e}")
            time.sleep(1.5)  # be polite
        except Exception as e:
            print(f"  ⚠ Wellfound query '{role} in {location}' failed: {e}")

    print(f"  → Wellfound total: {len(all_jobs)} jobs")
    return all_jobs
