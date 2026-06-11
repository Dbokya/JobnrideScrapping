"""
WeWorkRemotely RSS feed scraper — no API key required.
One of the largest remote-only job boards. Covers tech, product, design, etc.
Feeds: https://weworkremotely.com/categories/{category}.rss
"""
import requests
import time
import xml.etree.ElementTree as ET
from normalizer import (
    classify_job_for, clean_html, normalize_work_mode,
    extract_education, infer_functional_area, infer_industry,
    extract_skills_from_text, normalize_location,
)

SOURCE = "weworkremotely"

FEEDS = [
    ("programming",    "https://weworkremotely.com/categories/remote-programming-jobs.rss"),
    ("devops",         "https://weworkremotely.com/categories/remote-devops-sysadmin-jobs.rss"),
    ("management",     "https://weworkremotely.com/categories/remote-management-product-jobs.rss"),
    ("design",         "https://weworkremotely.com/categories/remote-design-jobs.rss"),
    ("data-science",   "https://weworkremotely.com/categories/remote-data-science-jobs.rss"),
    ("finance",        "https://weworkremotely.com/categories/remote-finance-legal-jobs.rss"),
    ("hr",             "https://weworkremotely.com/categories/remote-human-resources-jobs.rss"),
    ("marketing",      "https://weworkremotely.com/categories/remote-marketing-jobs.rss"),
    ("customer",       "https://weworkremotely.com/categories/remote-customer-support-jobs.rss"),
]

HEADERS = {"User-Agent": "JobNRideBot/2.0", "Accept": "application/rss+xml, application/xml"}


def fetch_feed(url: str, retries: int = 3) -> str:
    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=20)
            if resp.status_code == 200:
                return resp.text
            print(f"  ⚠ WWR feed HTTP {resp.status_code}: {url}")
            return ""
        except requests.exceptions.RequestException as e:
            wait = 2 ** attempt
            print(f"  ⚠ WWR network error (attempt {attempt}): {e}. Retry in {wait}s...")
            time.sleep(wait)
    return ""


def parse_feed(xml_text: str, category: str) -> list:
    jobs = []
    if not xml_text:
        return jobs
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        print(f"  ⚠ WWR XML parse error [{category}]: {e}")
        return jobs

    ns = ""
    channel = root.find("channel")
    if channel is None:
        return jobs

    for item in channel.findall("item"):
        try:
            title_el = item.find("title")
            link_el  = item.find("link")
            desc_el  = item.find("description")
            pub_el   = item.find("pubDate")
            region_el = item.find(f"{ns}region") if ns else None

            raw_title = (title_el.text or "").strip() if title_el is not None else ""
            apply_link = (link_el.text or "").strip() if link_el is not None else ""
            description_html = (desc_el.text or "") if desc_el is not None else ""
            pub_date = (pub_el.text or "").strip() if pub_el is not None else ""
            region = (region_el.text or "Worldwide").strip() if region_el is not None else "Worldwide"

            # WWR titles are often "Company: Job Title"
            if ": " in raw_title:
                company, title = raw_title.split(": ", 1)
            else:
                company, title = "", raw_title

            description_text = clean_html(description_html)
            location = normalize_location(region) if region else "Worldwide (Remote)"
            job_for = classify_job_for(title, description_text)
            skills_text = extract_skills_from_text(description_text)

            jobs.append({
                "title": title.strip(),
                "company": company.strip(),
                "location": location,
                "experience": "0-2 years" if job_for in ["intern", "fresher"] else "Not Specified",
                "jobType": "Remote",
                "salary": "Not Disclosed",
                "description": description_text[:5000] if description_text else "No description available.",
                "rawDescriptionHtml": description_html,
                "requirements": "Not Specified",
                "preferredSkills": skills_text,
                "responsibilities": "Not Specified",
                "applyLink": apply_link,
                "featuredImage": "",
                "source": f"weworkremotely/{category}",
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
                "notificationTitle": f"Remote Job at {company}" if company else f"Remote: {title[:40]}",
                "rawPostedDate": pub_date,
            })
        except Exception as e:
            print(f"  ⚠ WWR item parse error [{category}]: {e}")
    return jobs


def scrape() -> list:
    all_jobs = []
    seen_links: set = set()
    print(f"\n🌍 WeWorkRemotely: Fetching {len(FEEDS)} category feeds...")
    for category, url in FEEDS:
        xml_text = fetch_feed(url)
        jobs = parse_feed(xml_text, category)
        new = 0
        for job in jobs:
            link = job.get("applyLink", "")
            if not link or link in seen_links:
                continue
            seen_links.add(link)
            all_jobs.append(job)
            new += 1
        if new:
            print(f"  ✓ {category}: {new} jobs")
        time.sleep(0.4)
    print(f"  → WeWorkRemotely total: {len(all_jobs)} jobs")
    return all_jobs
