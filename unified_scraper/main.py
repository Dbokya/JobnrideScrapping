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
from normalizer import is_it_job, is_posted_today, today_ist, is_india_or_remote, is_english
from scrapers import (
    greenhouse, lever, ashby,
    workday, smartrecruiters, freshteam, wellfound,
    remotive, arbeitnow, himalayas, remoteok,
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
    # Global remote boards (any company, fully remote)
    "remotive":         True,   # Remote jobs worldwide
    "arbeitnow":        True,   # Remote-only (filtered)
    "himalayas":        True,   # Remote-first with salary
    "remoteok":         True,   # Any company, fully remote (remoteok.com)
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
    "remoteok":        remoteok.scrape,
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

    n_fetched   = len(all_jobs)

    # ── TODAY filter ─────────────────────────────────────────────────────────
    all_jobs = [j for j in all_jobs if is_posted_today(j.get("rawPostedDate", ""))]
    n_today     = len(all_jobs)

    # ── India + Remote filter ─────────────────────────────────────────────────
    all_jobs = [
        j for j in all_jobs
        if is_india_or_remote(j.get("country", ""), j.get("location", ""))
    ]
    n_location  = len(all_jobs)

    # ── English language filter ───────────────────────────────────────────────
    all_jobs = [
        j for j in all_jobs
        if is_english(j.get("title", ""), j.get("description", ""))
    ]
    n_english   = len(all_jobs)

    # ── IT filter ────────────────────────────────────────────────────────────
    if FILTER_IT_ONLY:
        all_jobs = [
            j for j in all_jobs
            if is_it_job(j.get("title", ""), j.get("description", ""), j.get("category", ""))
        ]
    n_it        = len(all_jobs)

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

    n_unique    = len(unique_jobs)

    # ── Sort: India → Remote → Other ─────────────────────────────────────────
    def _is_india(j):
        c = j.get("country", "").lower()
        wm = j.get("workMode", "").lower()
        loc = j.get("location", "").lower()
        if c in ("india", "in"):
            return True
        if wm == "remote" or c in ("remote", "worldwide"):
            return False
        # empty country: check location for India city names
        india_cities = {
            "india", "bangalore", "bengaluru", "mumbai", "pune", "hyderabad",
            "chennai", "delhi", "noida", "gurgaon", "gurugram", "kolkata",
        }
        return any(city in loc for city in india_cities)

    def _is_remote(j):
        return (
            j.get("workMode", "").lower() == "remote"
            or j.get("country", "").lower() in ("remote", "worldwide")
        )

    india_jobs  = [j for j in unique_jobs if _is_india(j)]
    remote_jobs = [j for j in unique_jobs if _is_remote(j) and not _is_india(j)]
    other_jobs  = [j for j in unique_jobs if not _is_india(j) and not _is_remote(j)]
    sorted_jobs = india_jobs + remote_jobs + other_jobs
    n_india  = len(india_jobs)
    n_remote = len(remote_jobs)

    # ── Save to Firebase ─────────────────────────────────────────────────────
    print(f"\n{'=' * 70}")
    print("💾 SAVING TO FIREBASE")
    print(f"{'=' * 70}")

    saved_count = 0
    skipped_count = 0
    error_count = 0
    last_saved_title = None
    last_saved_company = None
    source_saved: dict = {}   # top-level source name → saved count

    for job in sorted_jobs:
        try:
            saved = save_job(job, job_counter)
            # Normalize source key: "workday/infosys" → "workday"
            src_key = job.get("source", "unknown").split("/")[0]
            if saved:
                job_counter += 1
                saved_count += 1
                last_saved_title = job.get("title", "")
                last_saved_company = job.get("company", "")
                source_saved[src_key] = source_saved.get(src_key, 0) + 1
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
    print("📊 JOBNRIDE SCRAPER — FINAL REPORT")
    print(f"   Date : {today_ist()}  |  Run time : {elapsed}s")
    print(f"{'=' * 70}")
    print(f"   {'STEP':<38} {'JOBS':>6}")
    print(f"   {'-'*45}")
    print(f"   {'Fetched from all sources':<38} {n_fetched:>6}")
    print(f"   {'After today-only filter':<38} {n_today:>6}  (-{n_fetched - n_today})")
    print(f"   {'After India + Remote filter':<38} {n_location:>6}  (-{n_today - n_location})")
    print(f"   {'After English-only filter':<38} {n_english:>6}  (-{n_location - n_english})")
    print(f"   {'After IT-only filter':<38} {n_it:>6}  (-{n_english - n_it})")
    print(f"   {'After dedup':<38} {n_unique:>6}  (-{n_it - n_unique})")
    print(f"   {'  🇮🇳  India jobs ready':<38} {n_india:>6}")
    print(f"   {'  🌐  Remote jobs ready':<38} {n_remote:>6}")
    print(f"{'=' * 70}")
    print(f"   {'✅  NEW JOBS ADDED TO FIREBASE':<38} {saved_count:>6}")
    print(f"   {'⏭️   Skipped (already in DB)':<38} {skipped_count:>6}")
    print(f"   {'❌  Errors':<38} {error_count:>6}")
    print(f"{'=' * 70}")
    print(f"\n   {'SOURCE':<22} {'FETCHED':>8}  {'SAVED':>6}  {'TYPE'}")
    print(f"   {'-'*52}")
    for src, fetched in source_counts.items():
        saved_n  = source_saved.get(src, 0)
        src_type = "🇮🇳 India" if src in INDIA_FIRST_SOURCES else "🌐 Remote"
        status   = f"+{saved_n}" if saved_n else "—"
        print(f"   {src:<22} {fetched:>8}  {status:>6}  {src_type}")
    print(f"{'=' * 70}\n")


if __name__ == "__main__":
    run()
