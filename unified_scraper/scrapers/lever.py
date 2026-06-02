"""
Lever ATS public API scraper.
No API key required.
API: https://api.lever.co/v0/postings/{company}?mode=json
"""
import requests
import time
from normalizer import (
    normalize_experience, normalize_job_type, classify_job_for,
    clean_html, normalize_location, normalize_salary, normalize_skills,
    build_description,
)

SOURCE = "lever"

COMPANIES = [
    # ── India IT / Fintech ────────────────────────────────────────────────
    "groww", "phonepe", "razorpay", "cred", "zepto",
    "navi", "jupiter-money", "fi-money", "open",
    "paytm", "mobikwik", "bharatpe", "khatabook", "okcredit",
    "slice", "kreditbee", "lendingkart", "freo",
    "dunzo", "blinkit", "swiggy-instamart",
    "zetwerk", "moglix", "udaan", "ofbusiness",
    "vedantu", "testbook", "doubtnut", "classplus",
    "innovaccer", "niramai", "sigtuple", "qure-ai",
    "facilio", "bizongo", "ecozen",
    "mindtickle", "highradius", "whatfix", "zipteams",
    "vyapar", "zoho", "freshworks-lever",
    "cogoport", "freight-tiger", "blackbuck",
    "stanza-living", "colive", "nestaway",
    # ── India MNC Dev Centers ─────────────────────────────────────────────
    "thoughtworks", "sapient", "publicis-sapient",
    # Global Tech
    "atlassian", "netflix", "canva", "github", "dropbox",
    "eventbrite", "squarespace", "twitch", "pinterest",
    "lyft", "instacart", "grubhub", "doordash",
    "carta", "lattice", "gusto", "rippling",
    "benchling", "nerdio", "stytch", "courier",
    "airplane", "airplane-dev", "mercury", "brex",
    "dbt-labs", "prefect", "airbyte", "hightouch",
    "census", "fivetran", "stitch",
    "scale", "cohere", "weights-biases",
    "huggingface", "together", "perplexity",
    # E-comm / Retail
    "glossier", "warby-parker", "allbirds",
]


def fetch_jobs(company_slug: str, retries: int = 3) -> list:
    url = f"https://api.lever.co/v0/postings/{company_slug}?mode=json"
    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(url, timeout=15, headers={"User-Agent": "JobNRideBot/2.0"})
            if resp.status_code == 200:
                data = resp.json()
                return data if isinstance(data, list) else []
            if resp.status_code == 404:
                return []
            print(f"  ⚠ Lever {company_slug}: HTTP {resp.status_code}")
            return []
        except requests.exceptions.RequestException as e:
            wait = 2 ** attempt
            print(f"  ⚠ Network error for {company_slug} (attempt {attempt}): {e}. Retry in {wait}s...")
            time.sleep(wait)
    return []


def parse_job(raw: dict, company_slug: str) -> dict:
    title = raw.get("text", "").strip()
    apply_link = raw.get("hostedUrl", "") or raw.get("applyUrl", "")

    categories = raw.get("categories", {}) or {}
    location = normalize_location(categories.get("location", "") or raw.get("workplaceType", ""))
    team = categories.get("team", "")
    commitment = categories.get("commitment", "")  # Full-time, Part-time, Internship

    # Description from lists
    description_blocks = raw.get("descriptionPlain", "") or raw.get("description", "")
    description_text = clean_html(description_blocks) if "<" in str(description_blocks) else str(description_blocks)

    # Lists (responsibilities, requirements, etc.)
    lists = raw.get("lists", []) or []
    responsibilities = ""
    requirements = ""
    skills = ""
    for lst in lists:
        heading = (lst.get("text") or "").lower()
        content = clean_html(lst.get("content", "") or "")
        if any(w in heading for w in ["responsibilit", "what you'll do", "role", "duties", "what you will do"]):
            responsibilities = content[:1000]
        elif any(w in heading for w in ["requirement", "qualification", "what you need", "about you", "must have", "you have"]):
            requirements = content[:1000]
        elif any(w in heading for w in ["skill", "tech", "stack", "tools", "experience"]):
            skills = content[:500]

    # Also check additional field
    additional = clean_html(raw.get("additional", "") or "")

    company_name = company_slug.replace("-", " ").title()
    job_for = classify_job_for(title, description_text)
    job_type = normalize_job_type(commitment)
    loc_str = location or "Not Specified"

    full_description = build_description(
        raw=description_text,
        responsibilities=responsibilities,
        requirements=requirements,
        skills=skills,
        job_type=job_type,
        location=loc_str,
    )

    return {
        "title": title,
        "company": company_name,
        "location": loc_str,
        "experience": "0-2 years" if job_for in ["intern", "fresher"] else "Not Specified",
        "jobType": job_type,
        "salary": "Not Disclosed",
        "description": full_description,
        "requirements": requirements or "Not Specified",
        "preferredSkills": normalize_skills(skills),
        "responsibilities": responsibilities or "Not Specified",
        "applyLink": apply_link,
        "featuredImage": "",
        "source": f"lever/{company_slug}",
        "jobFor": job_for,
        "country": "",
        "category": team,
        "rawPostedDate": raw.get("createdAt") or raw.get("updatedAt") or "",
    }


def scrape() -> list:
    all_jobs = []
    print(f"\n⚙️  Lever: Scraping {len(COMPANIES)} companies...")
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
    print(f"  → Lever total: {len(all_jobs)} jobs")
    return all_jobs
