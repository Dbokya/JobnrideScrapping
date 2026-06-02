"""
Workday ATS scraper for major Indian IT companies.
Workday exposes a public JSON API for job listings — no API key needed.
POST https://{tenant}.wd{n}.myworkdayjobs.com/wday/cxs/{tenant}/{board}/jobs
"""
import requests
import time
from normalizer import (
    normalize_experience, normalize_job_type, classify_job_for,
    clean_html, normalize_location, normalize_skills,
    normalize_work_mode, extract_education, infer_functional_area, infer_industry,
)

SOURCE = "workday"

# Format: (company_display_name, tenant, wd_version, board_slug)
# These are verified public Workday job boards for Indian IT companies
COMPANIES = [
    # Big IT / Service Companies
    ("Infosys",         "infosys",          3,  "Infosys_Careers"),
    ("Wipro",           "wipro",            3,  "Wipro_Careers"),
    ("Capgemini",       "capgemini",        3,  "Capgemini"),
    ("Tech Mahindra",   "techmahindra",     3,  "TechMahindra"),
    ("Mphasis",         "mphasis",          5,  "Mphasis_External"),
    ("L&T Technology",  "ltts",             3,  "LTTS"),
    ("Hexaware",        "hexaware",         3,  "Hexaware"),
    ("Birlasoft",       "birlasoft",        3,  "Birlasoft_Careers"),
    ("Persistent",      "persistent",       3,  "Persistent_Systems"),
    ("KPIT",            "kpit",             3,  "KPIT_Careers"),
    ("Zensar",          "zensar",           3,  "Zensar_Technologies"),
    ("Cyient",          "cyient",           3,  "Cyient_Careers"),
    ("Mastek",          "mastek",           3,  "Mastek"),
    ("Sonata Software", "sonata",           3,  "Sonata_Software"),
    # Product / New Age
    ("Zomato",          "zomato",           3,  "Zomato"),
    ("Flipkart",        "flipkart",         3,  "Flipkart"),
    ("Paytm",           "paytm",            3,  "Paytm_Careers"),
    ("Ola",             "olacabs",          3,  "Ola_Careers"),
    ("MakeMyTrip",      "makemytrip",       3,  "MakeMyTrip"),
    ("InMobi",          "inmobi",           3,  "InMobi"),
    ("Freshworks",      "freshworks",       3,  "Freshworks"),
    ("Druva",           "druva",            3,  "Druva"),
    ("Mindtree",        "mindtreeltd",      3,  "Mindtree_Careers"),
    # MNCs with big India presence
    ("Accenture India", "accenture",        5,  "AccentureCareers"),
    ("IBM India",       "ibm",              3,  "IBM_Careers"),
    ("SAP India",       "sap",              3,  "SAP"),
    ("Oracle India",    "oracle",           5,  "OracleCareers"),
    ("Deloitte India",  "deloittedigital", 3,  "DeloitteDigital"),
    ("EY India",        "ey",               3,  "EY_Careers"),
    ("KPMG India",      "kpmg",             3,  "KPMG_Careers"),
    ("PwC India",       "pwc",              3,  "pwc"),
]

PAGE_SIZE = 20
MAX_PAGES = 10
HEADERS = {
    "User-Agent": "JobNRideBot/2.0",
    "Content-Type": "application/json",
    "Accept": "application/json",
}


def fetch_jobs_page(company_name: str, tenant: str, wd_ver: int, board: str,
                    offset: int, retries: int = 3) -> dict:
    url = f"https://{tenant}.wd{wd_ver}.myworkdayjobs.com/wday/cxs/{tenant}/{board}/jobs"
    payload = {
        "limit": PAGE_SIZE,
        "offset": offset,
        "searchText": "",
        "appliedFacets": {},
    }
    for attempt in range(1, retries + 1):
        try:
            resp = requests.post(url, json=payload, headers=HEADERS, timeout=20)
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code in [400, 404, 403]:
                return {}
            print(f"  ⚠ Workday {company_name}: HTTP {resp.status_code}")
            return {}
        except requests.exceptions.RequestException as e:
            wait = 2 ** attempt
            print(f"  ⚠ Workday {company_name} error (attempt {attempt}): {e}. Retry in {wait}s...")
            time.sleep(wait)
    return {}


def parse_job(raw: dict, company_name: str, tenant: str, wd_ver: int, board: str) -> dict:
    title = raw.get("title", "").strip()

    # Build apply link
    external_path = raw.get("externalPath", "")
    apply_link = (
        f"https://{tenant}.wd{wd_ver}.myworkdayjobs.com/en-US/{board}/job/{external_path}"
        if external_path else ""
    )

    # Location
    locations = raw.get("locationsText", "") or raw.get("locations", "")
    if isinstance(locations, list):
        locations = ", ".join([l.get("descriptor", "") for l in locations if l.get("descriptor")])
    location = normalize_location(str(locations)) if locations else "India"

    # Posted date
    posted_on = raw.get("postedOn", "")

    # Job type
    job_type_raw = raw.get("jobType", "") or raw.get("timeType", "")
    if isinstance(job_type_raw, dict):
        job_type_raw = job_type_raw.get("descriptor", "")

    # Category
    category = raw.get("jobCategory", "") or ""
    if isinstance(category, dict):
        category = category.get("descriptor", "")

    description_text = raw.get("jobDescription", {}).get("jobDescription", "") if isinstance(raw.get("jobDescription"), dict) else ""
    description_text = clean_html(description_text)

    job_for = classify_job_for(title, description_text)

    job_type = normalize_job_type(str(job_type_raw))
    category_str = str(category)

    return {
        "title": title,
        "company": company_name,
        "location": location,
        "experience": "0-2 years" if job_for in ["intern", "fresher"] else "Not Specified",
        "jobType": job_type,
        "salary": "Not Disclosed",
        "description": description_text[:5000] if description_text else "No description available.",
        "requirements": "Not Specified",
        "preferredSkills": "Not Specified",
        "responsibilities": "Not Specified",
        "applyLink": apply_link,
        "featuredImage": "",
        "source": f"workday/{company_name.lower().replace(' ', '_')}",
        "jobFor": job_for,
        "country": "India",
        "category": category_str,
        "workMode": normalize_work_mode(location, job_type),
        "functionalArea": infer_functional_area(title, category_str, description_text),
        "industry": infer_industry(company_name, category_str, title),
        "educationRequirement": extract_education(description_text),
        "noticePeriod": "Not Specified",
        "totalOpenings": "Not Specified",
        "benefits": "",
        "aboutCompany": "",
        "notificationTitle": f"New Job at {company_name}",
        "rawPostedDate": raw.get("postedOn") or raw.get("startDate") or "",
    }


def scrape_company(company_name: str, tenant: str, wd_ver: int, board: str) -> list:
    jobs = []
    offset = 0
    total = None

    while True:
        data = fetch_jobs_page(company_name, tenant, wd_ver, board, offset)
        if not data:
            break

        raw_jobs = data.get("jobPostings", [])
        if total is None:
            total = data.get("total", 0)

        if not raw_jobs:
            break

        for raw in raw_jobs:
            try:
                job = parse_job(raw, company_name, tenant, wd_ver, board)
                if job["title"] and job["applyLink"]:
                    jobs.append(job)
            except Exception as e:
                print(f"    ⚠ Parse error: {e}")

        offset += PAGE_SIZE
        if offset >= min(total or 0, MAX_PAGES * PAGE_SIZE):
            break
        time.sleep(0.4)

    return jobs


def scrape() -> list:
    all_jobs = []
    print(f"\n🏢 Workday India: Scraping {len(COMPANIES)} companies...")
    for company_name, tenant, wd_ver, board in COMPANIES:
        try:
            jobs = scrape_company(company_name, tenant, wd_ver, board)
            if jobs:
                print(f"  ✓ {company_name}: {len(jobs)} jobs")
                all_jobs.extend(jobs)
            time.sleep(0.5)
        except Exception as e:
            print(f"  ⚠ {company_name} failed: {e}")
    print(f"  → Workday India total: {len(all_jobs)} jobs")
    return all_jobs
