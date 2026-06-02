"""
JobNRide Firestore Cleanup
Deletes jobs that have:
  - Non-English title or description
  - Missing / too-short description (< 80 chars)
  - Placeholder description ("No description available.")
  - Empty or placeholder company name
  - Empty title
Runs before the main scraper so the collection stays clean.
"""
import sys
import time
from firebase_client import init_firebase
from normalizer import is_english

# Min description length to be considered "proper"
MIN_DESC_LEN = 80

BAD_DESCRIPTIONS = {
    "no description available.",
    "no description available",
    "not available",
    "n/a",
    "",
}

BAD_COMPANIES = {
    "not specified", "unknown", "n/a", "na", "company",
    "not available", "", "none",
}


def is_good_job(doc: dict) -> tuple[bool, str]:
    """Returns (keep, reason_if_bad)."""
    title = (doc.get("title") or "").strip()
    company = (doc.get("company") or "").strip()
    description = (doc.get("description") or "").strip()

    if not title:
        return False, "empty title"

    if company.lower() in BAD_COMPANIES:
        return False, f"bad company: {repr(company)}"

    desc_lower = description.lower()
    if desc_lower in BAD_DESCRIPTIONS:
        return False, "placeholder description"

    if len(description) < MIN_DESC_LEN:
        return False, f"description too short ({len(description)} chars)"

    if not is_english(title, description):
        return False, "non-English content"

    return True, ""


def run_cleanup():
    print("\n" + "=" * 70)
    print("🧹 JOBNRIDE FIRESTORE CLEANUP")
    print("=" * 70)

    db = init_firebase()

    print("\n📋 Scanning Directjobs collection...")
    # Only scan API-scraped jobs (apijob prefix), not manually posted ones
    docs = list(
        db.collection("Directjobs")
        .where("sourceFile", "==", "unified_scraper")
        .stream()
    )
    print(f"   Found {len(docs)} unified_scraper jobs to evaluate")

    delete_count = 0
    keep_count = 0
    reasons: dict[str, int] = {}

    for doc in docs:
        data = doc.to_dict()
        keep, reason = is_good_job(data)
        if keep:
            keep_count += 1
        else:
            reasons[reason] = reasons.get(reason, 0) + 1
            try:
                db.collection("Directjobs").document(doc.id).delete()
                delete_count += 1
                title = (data.get("title") or "")[:50]
                print(f"  🗑️  Deleted [{data.get('jobid','')}] {title!r} — {reason}")
            except Exception as e:
                print(f"  ❌ Failed to delete {doc.id}: {e}")
            time.sleep(0.05)  # avoid Firestore rate limit

    print(f"\n{'=' * 70}")
    print("🧹 CLEANUP SUMMARY")
    print(f"{'=' * 70}")
    print(f"   Evaluated  : {len(docs)} jobs")
    print(f"   ✅ Kept    : {keep_count}")
    print(f"   🗑️  Deleted : {delete_count}")
    if reasons:
        print("   Reasons:")
        for reason, count in sorted(reasons.items(), key=lambda x: -x[1]):
            print(f"     • {reason}: {count}")
    print(f"{'=' * 70}\n")

    return delete_count


if __name__ == "__main__":
    run_cleanup()
