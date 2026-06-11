"""
The Muse API scraper.
Free API key available at: https://www.themuse.com/developers/api/v2
Env var: THEMUSE_API_KEY (optional — works without key at lower rate limit)
API: https://www.themuse.com/api/public/jobs
"""
import os
import requests
import time
from normalizer import (
    normalize_job_type, classify_job_for,
    clean_html, normalize_location, normalize_skills,
    normalize_work_mode, extract_education, infer_functional_area, infer_industry,
)

SOURCE = "themuse"
API_URL = "https://www.themuse.com/api/public/jobs"
API_KEY = os.getenv("THEMUSE_API_KEY", "")
MAX_PAGES = 10
PAGE_SIZE = 20


def fetch_page(page: int, retries: int = 3) -> dict:
    params = {"page": page, "descending": "true"}
    if API_KEY:
        params["api_key"] = API_KEY
    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(API_URL, params=params, timeout=20, headers={"User-Agent": "JobNRideBot/2.0"})
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code == 429:
                print("  ⚠ The Muse: Rate limited. Waiting 10s...")
                time.sleep(10)
                continue
            return {}
        except requests.exceptions.RequestException as e:
            wait = 2 ** attempt
            print(f"  ⚠ The Muse error (attempt {attempt}): {e}. Retry in {wait}s...")
            time.sleep(wait)
    return {}


def parse_job(raw: dict) -> dict:
    title = raw.get("name", "").strip()

    company_data = raw.get("company", {}) or {}
    company = company_data.get("name", "").strip()

    locations = raw.get("locations", []) or []
    location_names = [loc.get("name", "") for loc in locations if loc.get("name")]
    location = normalize_location(", ".join(location_names)) if location_names else "USA"
    is_remote = any(
        "remote" in ln.lower() or "flexible" in ln.lower() or "anywhere" in ln.lower()
        for ln in location_names
    )

    levels = raw.get("levels", []) or []
    level_names = [l.get("name", "") for l in levels]
    level_str = ", ".join(level_names)

    categories = raw.get("categories", []) or []
    cat_names = [c.get("name", "") for c in categories]
    category = ", ".join(cat_names)

    contents = raw.get("contents", "")
    description_text = clean_html(contents) if contents else ""
    apply_link = raw.get("refs", {}).get("landing_page", "") or raw.get("job_url", "")

    publication_date = raw.get("publication_date", "")

    job_for = classify_job_for(title, description_text)

    # Infer experience from level
    exp = "Not Specified"
    if level_str:
        ll = level_str.lower()
        if "intern" in ll:
            exp = "0-2 years"
        elif "entry" in ll or "junior" in ll:
            exp = "0-2 years"
        elif "mid" in ll:
            exp = "2-5 years"
        elif "senior" in ll or "lead" in ll:
            exp = "5-10 years"
        elif "director" in ll or "vp" in ll or "head" in ll:
            exp = "10+ years"

    job_type = "Internship" if job_for == "intern" else "Full-Time"
    company_name = company or "Not Specified"
    logo = company_data.get("refs", {}).get("logo_image", "") if isinstance(company_data.get("refs"), dict) else ""
    country_val = "Remote" if is_remote else "USA"
    
    # Extract skills from description, category, and levels
    skills_text = extract_skills_from_text(description_text)
    if not skills_text or skills_text == "Not Specified":
        skills_text = extract_skills_from_text(f"{category} {level_str}")

    return {
        "title": title,
        "company": company_name,
        "location": location,
        "experience": exp,
        "jobType": job_type,
        "salary": "Not Disclosed",
        "description": description_text[:5000] if description_text else "No description available.",
        "rawDescriptionHtml": contents,
        "requirements": "Not Specified",
        "preferredSkills": skills_text,
        "responsibilities": "Not Specified",
        "applyLink": apply_link,
        "featuredImage": logo,
        "companyLogo": logo,
        "source": "themuse",
        "jobFor": job_for,
        "country": country_val,
        "workMode": "Remote" if is_remote else "On-site",
        "functionalArea": infer_functional_area(title, category, description_text),
        "industry": infer_industry(company_name, category, title),
        "educationRequirement": extract_education(description_text),
        "noticePeriod": "Not Specified",
        "totalOpenings": "Not Specified",
        "benefits": "",
        "aboutCompany": "",
        "notificationTitle": f"Remote Job at {company_name}" if is_remote else f"New Job at {company_name}",
        "_is_remote": is_remote,
        "category": category,
        "rawPostedDate": publication_date,
    }


def scrape() -> list:
    all_jobs = []
    print(f"\n🎯 The Muse: Fetching jobs...")
    for page in range(0, MAX_PAGES):
        data = fetch_page(page)
        raw_jobs = data.get("results", [])
        if not raw_jobs:
            break
        print(f"  ✓ Page {page + 1}: {len(raw_jobs)} jobs")
        for raw in raw_jobs:
            try:
                job = parse_job(raw)
                # Only include remote/flexible jobs from The Muse (US-based source)
                if not job.pop("_is_remote", False):
                    continue
                if job["title"] and job["applyLink"]:
                    all_jobs.append(job)
            except Exception as e:
                print(f"  ⚠ The Muse parse error: {e}")
        time.sleep(0.8)  # be polite to avoid rate limiting
    print(f"  → The Muse total: {len(all_jobs)} jobs")
    return all_jobs
