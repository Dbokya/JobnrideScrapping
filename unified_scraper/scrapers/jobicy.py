"""
Jobicy public API scraper — no API key required.
Remote tech jobs globally, includes India-tagged roles.
API: https://jobicy.com/api/v2/remote-jobs
"""
import requests
import time
from normalizer import (
    normalize_job_type, classify_job_for, clean_html,
    normalize_salary, normalize_work_mode, extract_education,
    infer_functional_area, infer_industry, extract_skills_from_text,
    normalize_location,
)

SOURCE = "jobicy"
API_URL = "https://jobicy.com/api/v2/remote-jobs"

# Tech-relevant tags to query
TAGS = [
    "software-engineer", "backend", "frontend", "fullstack",
    "devops", "data-engineer", "data-scientist", "machine-learning",
    "mobile", "android", "ios", "cloud", "security",
    "product-manager", "qa", "java", "python", "javascript",
    "react", "node", "golang", "ruby", "php",
]


def fetch_jobs(tag: str, retries: int = 3) -> list:
    params = {"count": 50, "tag": tag}
    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(
                API_URL, params=params, timeout=20,
                headers={"User-Agent": "JobNRideBot/2.0"},
            )
            if resp.status_code == 200:
                return resp.json().get("jobs", [])
            if resp.status_code == 429:
                time.sleep(5)
                continue
            print(f"  ⚠ Jobicy [{tag}]: HTTP {resp.status_code}")
            return []
        except requests.exceptions.RequestException as e:
            wait = 2 ** attempt
            print(f"  ⚠ Jobicy network error (attempt {attempt}): {e}. Retry in {wait}s...")
            time.sleep(wait)
    return []


def parse_job(raw: dict) -> dict:
    title = raw.get("jobTitle", "").strip()
    company = raw.get("companyName", "").strip()
    apply_link = raw.get("url", "")
    logo = raw.get("companyLogo", "")
    location_raw = raw.get("jobGeo", "Worldwide") or "Worldwide"
    location = normalize_location(location_raw)
    job_type_raw = raw.get("jobType", "")
    salary_raw = raw.get("annualSalaryMin", "") or raw.get("annualSalaryMax", "")
    description_html = raw.get("jobDescription", "") or raw.get("jobExcerpt", "")
    description_text = clean_html(description_html)
    industry = raw.get("jobIndustry", [])
    if isinstance(industry, list):
        industry = ", ".join(industry)
    pub_date = raw.get("pubDate", "")

    job_for = classify_job_for(title, description_text)
    job_type = normalize_job_type(job_type_raw) if job_type_raw else "Remote"
    loc_str = f"{location} (Remote)" if "remote" not in location.lower() else location
    skills_text = extract_skills_from_text(description_text)

    salary_str = "Not Disclosed"
    if salary_raw:
        try:
            salary_str = f"${int(salary_raw):,}/yr"
        except (ValueError, TypeError):
            pass

    return {
        "title": title,
        "company": company,
        "location": loc_str,
        "experience": "0-2 years" if job_for in ["intern", "fresher"] else "Not Specified",
        "jobType": job_type,
        "salary": salary_str,
        "description": description_text[:5000] if description_text else "No description available.",
        "rawDescriptionHtml": description_html,
        "requirements": "Not Specified",
        "preferredSkills": skills_text,
        "responsibilities": "Not Specified",
        "applyLink": apply_link,
        "featuredImage": logo or "",
        "companyLogo": logo or "",
        "source": "jobicy",
        "jobFor": job_for,
        "country": "Remote",
        "category": industry,
        "workMode": "Remote",
        "functionalArea": infer_functional_area(title, industry, description_text),
        "industry": infer_industry(company, industry, title),
        "educationRequirement": extract_education(description_text),
        "noticePeriod": "Not Specified",
        "totalOpenings": "Not Specified",
        "benefits": "",
        "aboutCompany": "",
        "notificationTitle": f"Remote Job at {company}",
        "rawPostedDate": pub_date,
    }


def scrape() -> list:
    all_jobs = []
    seen_urls: set = set()
    print(f"\n💼 Jobicy: Fetching remote jobs across {len(TAGS)} tags...")
    for tag in TAGS:
        raw_jobs = fetch_jobs(tag)
        for raw in raw_jobs:
            try:
                url = raw.get("url", "")
                if not url or url in seen_urls:
                    continue
                seen_urls.add(url)
                job = parse_job(raw)
                if job["title"] and job["applyLink"]:
                    all_jobs.append(job)
            except Exception as e:
                print(f"  ⚠ Jobicy parse error: {e}")
        time.sleep(0.5)
    print(f"  → Jobicy total: {len(all_jobs)} jobs")
    return all_jobs
