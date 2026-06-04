"""
ATS Discovery Tool — find the verified public job-board slug for any company.

For each company name we generate slug candidates and probe every supported
public ATS API. We report only endpoints that actually return live jobs, so the
company lists in scrapers/ can be filled with VERIFIED slugs instead of guesses.

Usage:
    python discover_ats.py                # probe the built-in TARGETS list
    python discover_ats.py "Amdocs" "TCS" # probe specific company names
"""
import sys
import re
import time
import requests

HEADERS = {"User-Agent": "JobNRideBot/2.0", "Accept": "application/json"}
TIMEOUT = 12


def slug_variants(name: str):
    """Generate plausible ATS slug candidates from a display name."""
    base = name.strip().lower()
    # strip common suffixes
    base = re.sub(r"\b(technologies|technology|solutions|systems|software|"
                  r"limited|ltd|inc|corp|global|india|pvt|private)\b", "", base)
    base = base.strip()
    compact = re.sub(r"[^a-z0-9]", "", base)
    hyphen = re.sub(r"[^a-z0-9]+", "-", base).strip("-")
    full_compact = re.sub(r"[^a-z0-9]", "", name.lower())
    full_hyphen = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    out = []
    for s in (compact, hyphen, full_compact, full_hyphen):
        if s and s not in out:
            out.append(s)
    return out


# ── Per-ATS probes: return job count if the slug is a live board, else None ──

def probe_greenhouse(slug):
    url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        if r.status_code == 200:
            n = len(r.json().get("jobs", []))
            return n if n else None
    except requests.RequestException:
        pass
    return None


def probe_lever(slug):
    url = f"https://api.lever.co/v0/postings/{slug}?mode=json"
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        if r.status_code == 200 and isinstance(r.json(), list):
            n = len(r.json())
            return n if n else None
    except requests.RequestException:
        pass
    return None


def probe_ashby(slug):
    url = f"https://api.ashbyhq.com/posting-api/job-board/{slug}"
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        if r.status_code == 200:
            d = r.json()
            n = len(d.get("jobs", d.get("jobPostings", [])))
            return n if n else None
    except requests.RequestException:
        pass
    return None


def probe_smartrecruiters(slug):
    url = f"https://api.smartrecruiters.com/v1/companies/{slug}/postings?limit=1"
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        if r.status_code == 200:
            n = r.json().get("totalFound", 0)
            return n if n else None
    except requests.RequestException:
        pass
    return None


def probe_recruitee(slug):
    url = f"https://{slug}.recruitee.com/api/offers/"
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        if r.status_code == 200:
            n = len(r.json().get("offers", []))
            return n if n else None
    except requests.RequestException:
        pass
    return None


PROBES = {
    "greenhouse":      probe_greenhouse,
    "lever":           probe_lever,
    "ashby":           probe_ashby,
    "smartrecruiters": probe_smartrecruiters,
    "recruitee":       probe_recruitee,
}


def discover(name: str):
    """Return list of (ats, slug, job_count) for every live board found."""
    hits = []
    seen = set()
    for slug in slug_variants(name):
        for ats, probe in PROBES.items():
            key = (ats, slug)
            if key in seen:
                continue
            seen.add(key)
            n = probe(slug)
            if n:
                hits.append((ats, slug, n))
            time.sleep(0.15)
    return hits


# Major India / India-presence employers to locate. Extend freely.
TARGETS = [
    "Amdocs", "Nagarro", "Mphasis", "Cognizant", "Capgemini", "Sapient",
    "Publicis Sapient", "ThoughtWorks", "EPAM", "Globant", "Luxoft",
    "GlobalLogic", "Encora", "Synechron", "Iris Software", "Brillio",
    "Tiger Analytics", "Fractal Analytics", "Mu Sigma", "LatentView",
    "Sprinklr", "Druva", "Postman", "BrowserStack", "Hasura", "Chargebee",
    "Freshworks", "Zoho", "Razorpay", "PhonePe", "Groww", "Zerodha",
    "Swiggy", "Zomato", "Meesho", "Flipkart", "Nykaa", "CRED", "Zepto",
    "Navi", "Slice", "Juspay", "Cashfree", "Setu", "Decentro", "M2P",
    "Innovaccer", "Whatfix", "MindTickle", "HighRadius", "Gupshup",
    "Sprinto", "Atlan", "Hevo Data", "Rippling", "Deel", "Turing",
    "Persistent Systems", "Coforge", "Birlasoft", "Cyient", "KPIT",
    "Zensar", "Mastek", "Sonata Software", "Happiest Minds", "Newgen",
    "Intellect Design", "Ramco Systems", "Subex", "Tata Elxsi",
]


def main():
    names = sys.argv[1:] or TARGETS
    print(f"🔎 Probing {len(names)} companies across {len(PROBES)} ATS platforms...\n")
    found = {}
    for name in names:
        hits = discover(name)
        if hits:
            best = ", ".join(f"{a}:{s} ({n})" for a, s, n in hits)
            print(f"  ✅ {name:<22} → {best}")
            found[name] = hits
        else:
            print(f"  ❌ {name:<22} → no public ATS board found")

    print(f"\n{'='*60}")
    print(f"Found public boards for {len(found)}/{len(names)} companies.\n")

    # Emit copy-paste-ready slug lists per ATS
    per_ats = {ats: [] for ats in PROBES}
    for name, hits in found.items():
        for ats, slug, n in hits:
            per_ats[ats].append((slug, name, n))
    for ats, rows in per_ats.items():
        if not rows:
            continue
        print(f"# --- {ats} ---")
        for slug, name, n in sorted(rows, key=lambda x: -x[2]):
            print(f'    "{slug}",  # {name} ({n} jobs)')
        print()


if __name__ == "__main__":
    main()
