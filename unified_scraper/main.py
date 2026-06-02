"""
JobNRide Unified Job Scraper — India IT Focus
Sources: Greenhouse, Lever, Ashby, Workday, SmartRecruiters, Freshteam,
         Wellfound, Remotive, Arbeitnow, Himalayas, Adzuna, The Muse
Posts to Firebase Firestore > Directjobs collection
Sends FCM push notification when new jobs are added
"""
import sys
import time
from datetime import datetime
import pytz

from firebase_client import init_firebase, save_job, get_highest_api_id, send_notification
from normalizer import is_it_job, is_posted_today, today_ist
from scrapers import (
    greenhouse, lever, ashby,
    workday, smartrecruiters, freshteam, wellfound,
    remotive, arbeitnow, himalayas,
    adzuna, themuse,
)

IST = pytz.timezone("Asia/Kolkata")

# ─── Source toggle — set False to disable a source ─────────────────────────
SOURCES = {
    # India-first sources (highest priority)
    "workday":          True,   # Infosys, Wipro, Capgemini, Zomato, Flipkart...
    "smartrecruiters":  True,   # HCL, Cognizant, OYO, Nykaa...
    "freshteam":        True,   # Razorpay, Zepto, Groww, BrowserStack, Byju's...
    "wellfound":        True,   # Indian startups (AngelList Talent)
    # ATS boards — India + Global
    "greenhouse":       True,   # Swiggy, Stripe, Notion, Freshworks...
    "lever":            True,   # PhonePe, Groww, Atlassian, Canva...
    "ashby":            True,   # Linear, Vercel, Anthropic, Cursor...
    # Global remote boards
    "remotive":         True,   # Remote jobs worldwide
    "arbeitnow":        True,   # EU + Remote
    "himalayas":        True,   # Remote-first with salary
    # Optional (need free API keys)
    "adzuna":           True,   # India + 6 other countries (needs ADZUNA_APP_ID/KEY)
    "themuse":          True,   # US companies
}

SCRAPER_MAP = {
    "workday":         workday.scrape,
    "smartrecruiters": smartrecruiters.scrape,
    "freshteam":       freshteam.scrape,
    "wellfound":       wellfound.scrape,
    "greenhouse":      greenhouse.scrape,
    "lever":           lever.scrape,
    "ashby":           ashby.scrape,
    "remotive":        remotive.scrape,
    "arbeitnow":       arbeitnow.scrape,
    "himalayas":       himalayas.scrape,
    "adzuna":          adzuna.scrape,
    "themuse":         themuse.scrape,
}

# IT filter — set to True to only save IT/tech jobs
FILTER_IT_ONLY = True

# India filter — set to True to prefer India jobs (still saves remote/global)
INDIA_FIRST_SOURCES = {"workday", "smartrecruiters", "freshteam", "wellfound", "adzuna"}


def run():
    start_time = time.time()
    now = datetime.now(IST)

    print("\n" + "=" * 70)
    print("🚀 JOBNRIDE UNIFIED SCRAPER — INDIA IT FOCUS")
    print(f"   Started : {now.strftime('%Y-%m-%d %H:%M:%S IST')}")
    print(f"   IT Filter: {'ON' if FILTER_IT_ONLY else 'OFF'}")
    print("=" * 70)

    # Init Firebase
    print("\n🔥 Initializing Firebase...")
    try:
        init_firebase()
        print("   ✓ Firebase connected")
    except Exception as e:
        print(f"   ❌ Firebase init failed: {e}")
        sys.exit(1)

    highest_id = get_highest_api_id()
    job_counter = highest_id + 1
    print(f"   ✓ Next job ID: apijob{job_counter:04d}")

    # ── Collect jobs from all sources ───────────────────────────────────────
    all_jobs = []
    source_counts = {}

    for source_name, enabled in SOURCES.items():
        if not enabled:
            print(f"\n⏭️  Skipping {source_name} (disabled)")
            continue
        scrape_fn = SCRAPER_MAP[source_name]
        try:
            jobs = scrape_fn()
            source_counts[source_name] = len(jobs)
            all_jobs.extend(jobs)
        except Exception as e:
            print(f"\n❌ {source_name} scraper crashed: {e}")
            source_counts[source_name] = 0

    print(f"\n{'=' * 70}")
    print(f"📦 Total collected across all sources : {len(all_jobs)}")

    # ── TODAY filter — only keep jobs posted today (IST) ─────────────────────
    before_date = len(all_jobs)
    all_jobs = [j for j in all_jobs if is_posted_today(j.get("rawPostedDate", ""))]
    dropped_date = before_date - len(all_jobs)
    print(f"📅 Today's jobs only ({today_ist()})        : {len(all_jobs)} (dropped {dropped_date} older jobs)")

    # ── IT filter ────────────────────────────────────────────────────────────
    if FILTER_IT_ONLY:
        before = len(all_jobs)
        all_jobs = [
            j for j in all_jobs
            if is_it_job(j.get("title", ""), j.get("description", ""), j.get("category", ""))
        ]
        print(f"🔍 After IT filter                    : {len(all_jobs)} (removed {before - len(all_jobs)} non-IT jobs)")

    # ── Deduplicate within this batch (same applyLink) ───────────────────────
    seen_links = set()
    unique_jobs = []
    for job in all_jobs:
        link = job.get("applyLink", "")
        if link and link in seen_links:
            continue
        if link:
            seen_links.add(link)
        unique_jobs.append(job)

    print(f"🔁 After in-batch dedup               : {len(unique_jobs)} unique jobs")
    print(f"{'=' * 70}")

    # ── Sort: India jobs first ────────────────────────────────────────────────
    india_jobs = [j for j in unique_jobs if j.get("country", "").lower() in ["india", "in", ""]]
    other_jobs = [j for j in unique_jobs if j not in india_jobs]
    sorted_jobs = india_jobs + other_jobs
    print(f"🇮🇳 India jobs: {len(india_jobs)}  |  🌍 Other: {len(other_jobs)}")

    # ── Save to Firebase ─────────────────────────────────────────────────────
    print(f"\n{'=' * 70}")
    print("💾 SAVING TO FIREBASE")
    print(f"{'=' * 70}")

    saved_count = 0
    skipped_count = 0
    error_count = 0
    last_saved_title = None
    last_saved_company = None

    for job in sorted_jobs:
        try:
            saved = save_job(job, job_counter)
            if saved:
                job_counter += 1
                saved_count += 1
                last_saved_title = job.get("title", "")
                last_saved_company = job.get("company", "")
            else:
                skipped_count += 1
        except Exception as e:
            print(f"  ❌ Error saving '{job.get('title','')}': {e}")
            error_count += 1
        time.sleep(0.1)

    # ── FCM Push Notification ────────────────────────────────────────────────
    if saved_count > 0 and last_saved_title:
        try:
            notif_title = "🚀 New IT Jobs Alert!"
            notif_body = (
                f"{saved_count} new IT job{'s' if saved_count > 1 else ''} added! "
                f"Latest: {last_saved_title[:40]} @ {last_saved_company}"
            )
            send_notification(notif_title, notif_body)
        except Exception as e:
            print(f"\n⚠ Notification failed: {e}")
    else:
        print("\n⏭️  No new jobs — notification skipped.")

    # ── Final Summary ────────────────────────────────────────────────────────
    elapsed = round(time.time() - start_time, 1)

    print(f"\n{'=' * 70}")
    print("📊 FINAL SUMMARY")
    print(f"{'=' * 70}")
    print(f"   Date (IST)         : {today_ist()}")
    print(f"   Run Time           : {elapsed}s")
    print(f"   Jobs Collected     : {len(all_jobs)}")
    print(f"   After Today Filter : (today only)")
    print(f"   After IT Filter    : {len(unique_jobs)}")
    print(f"   🇮🇳 India Jobs     : {len(india_jobs)}")
    print(f"   ✅ Saved to DB     : {saved_count}")
    print(f"   ⏭️  Skipped (dup)  : {skipped_count}")
    print(f"   ❌ Errors          : {error_count}")
    print(f"{'=' * 70}")
    print("   Per-source:")
    for src, count in source_counts.items():
        flag = "🇮🇳" if src in INDIA_FIRST_SOURCES else "🌍"
        print(f"     {flag} {src:<18}: {count} jobs fetched")
    print(f"{'=' * 70}\n")


if __name__ == "__main__":
    run()
