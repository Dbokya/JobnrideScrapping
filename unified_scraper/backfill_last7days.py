"""
backfill_last7days.py — Re-parse and fix all Directjobs from the last 7 days.

For every job saved in the last 7 days this script:
  1. Runs Phase 1 (BeautifulSoup) on rawDescriptionHtml if available
  2. Runs GPT-4o mini to extract:
       - clean description summary (2-3 sentences)
       - responsibilities (bullet points)
       - requirements (bullet points)
       - salary (actual value)
       - experience (e.g. "3-5 years")
       - skills (comma-separated)
       - benefits
       - aboutCompany
  3. Updates only the fields that were empty / "Not Specified" / "Not Disclosed"
     so existing good data is never overwritten.

Usage:
    cd unified_scraper
    OPEN_AI_API_KEY=sk-... python backfill_last7days.py
"""

import time
from datetime import datetime, timedelta
import pytz
from firebase_client import init_firebase
from ai_parser import parse_job_sections
from normalizer import extract_skills_from_text

IST = pytz.timezone("Asia/Kolkata")
DAYS_BACK = 7
BATCH_SLEEP = 0.3   # seconds between Firestore writes (rate-limit safety)

EMPTY_VALUES = {"", "not specified", "not disclosed", "n/a", "na",
                "no description available.", "no description available"}


def _is_empty(val) -> bool:
    return not val or str(val).strip().lower() in EMPTY_VALUES


def _build_update(job: dict, ai: dict) -> dict:
    """
    Build a Firestore update dict.
    Only fills fields that are currently empty/placeholder.
    Never overwrites existing good data.
    """
    update = {}

    # ── Description: replace blob with clean summary ─────────────────────────
    ai_desc = (ai.get("description") or "").strip()
    if ai_desc and len(ai_desc) > 20:
        # Always update description with the AI summary (cleaner than raw blob)
        update["description"] = ai_desc

    # ── Responsibilities ──────────────────────────────────────────────────────
    if _is_empty(job.get("responsibilities")):
        val = (ai.get("responsibilities") or "").strip()
        if val:
            update["responsibilities"] = val

    # ── Requirements ─────────────────────────────────────────────────────────
    if _is_empty(job.get("requirements")):
        val = (ai.get("requirements") or "").strip()
        if val:
            update["requirements"] = val

    # ── Salary ───────────────────────────────────────────────────────────────
    if _is_empty(job.get("salary")):
        val = (ai.get("salary") or "").strip()
        if val:
            update["salary"] = val

    # ── Experience ───────────────────────────────────────────────────────────
    if _is_empty(job.get("experience")):
        val = (ai.get("experience") or "").strip()
        if val:
            update["experience"] = val

    # ── Benefits ─────────────────────────────────────────────────────────────
    if _is_empty(job.get("benefits")):
        val = (ai.get("benefits") or "").strip()
        if val:
            update["benefits"] = val

    # ── About company ────────────────────────────────────────────────────────
    if _is_empty(job.get("aboutCompany")):
        val = (ai.get("aboutCompany") or "").strip()
        if val:
            update["aboutCompany"] = val

    # ── Skills: merge AI skills with existing regex skills ───────────────────
    ai_skills = (ai.get("skills") or "").strip()
    existing_skills = (job.get("preferredSkills") or "").strip()

    if ai_skills:
        if _is_empty(existing_skills):
            merged = ai_skills
        else:
            # Merge without duplicates (case-insensitive)
            existing_set = {s.strip().lower() for s in existing_skills.split(",")}
            new_skills = [s.strip() for s in ai_skills.split(",")
                          if s.strip() and s.strip().lower() not in existing_set]
            merged = existing_skills + (", " + ", ".join(new_skills) if new_skills else "")

        if merged and merged != existing_skills:
            update["preferredSkills"] = merged
            update["skill"] = merged
            update["keySkills"] = [s.strip() for s in merged.split(",") if s.strip()]

    return update


def run_backfill():
    print("\n" + "=" * 70)
    print("🔄 JOBNRIDE 7-DAY BACKFILL — AI Field Extraction")
    print("=" * 70)

    db = init_firebase()

    cutoff = datetime.now(IST) - timedelta(days=DAYS_BACK)
    print(f"\n📅 Fetching jobs since: {cutoff.strftime('%Y-%m-%d %H:%M IST')}")

    docs = list(
        db.collection("Directjobs")
        .where("sourceFile", "==", "unified_scraper")
        .where("createdAt", ">=", cutoff)
        .stream()
    )
    print(f"   Found {len(docs)} jobs to process\n")

    updated = 0
    skipped = 0
    errors  = 0

    for i, doc in enumerate(docs, 1):
        job = doc.to_dict()
        title   = (job.get("title") or "")[:60]
        company = (job.get("company") or "")[:30]
        jobid   = job.get("jobid", doc.id)

        print(f"[{i:03d}/{len(docs)}] {jobid} — {title} @ {company}")

        raw_html   = job.get("rawDescriptionHtml", "")
        plain_text = job.get("description", "")

        # Skip if no content to parse
        if not raw_html and (not plain_text or len(plain_text.strip()) < 80):
            print(f"         ⏭  Skipped — no content")
            skipped += 1
            continue

        try:
            ai = parse_job_sections(raw_html=raw_html, plain_text=plain_text)

            if not ai:
                print(f"         ⚠  AI returned nothing")
                skipped += 1
                continue

            update = _build_update(job, ai)

            if not update:
                print(f"         ✓  Already complete — nothing to update")
                skipped += 1
                continue

            db.collection("Directjobs").document(doc.id).update(update)
            fields_updated = list(update.keys())
            print(f"         ✅ Updated: {', '.join(fields_updated)}")
            updated += 1

        except Exception as e:
            print(f"         ❌ Error: {e}")
            errors += 1

        time.sleep(BATCH_SLEEP)

    print(f"\n{'=' * 70}")
    print("📊 BACKFILL SUMMARY")
    print(f"{'=' * 70}")
    print(f"   Total jobs  : {len(docs)}")
    print(f"   ✅ Updated  : {updated}")
    print(f"   ⏭  Skipped  : {skipped}")
    print(f"   ❌ Errors   : {errors}")
    print(f"{'=' * 70}\n")


if __name__ == "__main__":
    run_backfill()
