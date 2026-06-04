"""
Slug Audit — probe every hardcoded company slug in the scrapers and report
which ones are ALIVE (return jobs) vs DEAD (404 / 422 / 0 jobs).

Reads the real COMPANIES lists from each scraper module so the audit always
matches what production actually runs. Use the DEAD report to prune the lists.

Usage:
    python audit_slugs.py            # audit everything
    python audit_slugs.py greenhouse # audit one platform
"""
import sys
import time
import requests

from scrapers import greenhouse, lever, ashby, smartrecruiters, workday

HEADERS = {"User-Agent": "JobNRideBot/2.0", "Accept": "application/json"}
TIMEOUT = 12


def probe_greenhouse(slug):
    try:
        r = requests.get(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs",
                         headers=HEADERS, timeout=TIMEOUT)
        if r.status_code == 200:
            return len(r.json().get("jobs", []))
    except requests.RequestException:
        return None
    return 0


def probe_lever(slug):
    try:
        r = requests.get(f"https://api.lever.co/v0/postings/{slug}?mode=json",
                         headers=HEADERS, timeout=TIMEOUT)
        if r.status_code == 200 and isinstance(r.json(), list):
            return len(r.json())
    except requests.RequestException:
        return None
    return 0


def probe_ashby(slug):
    try:
        r = requests.get(f"https://api.ashbyhq.com/posting-api/job-board/{slug}",
                         headers=HEADERS, timeout=TIMEOUT)
        if r.status_code == 200:
            d = r.json()
            return len(d.get("jobs", d.get("jobPostings", [])))
    except requests.RequestException:
        return None
    return 0


def probe_smartrecruiters(slug):
    try:
        r = requests.get(f"https://api.smartrecruiters.com/v1/companies/{slug}/postings?limit=1",
                         headers=HEADERS, timeout=TIMEOUT)
        if r.status_code == 200:
            return r.json().get("totalFound", 0)
    except requests.RequestException:
        return None
    return 0


def probe_workday(tenant, ver, board):
    url = f"https://{tenant}.wd{ver}.myworkdayjobs.com/wday/cxs/{tenant}/{board}/jobs"
    payload = {"limit": 1, "offset": 0, "searchText": "", "appliedFacets": {}}
    try:
        r = requests.post(url, json=payload, headers={**HEADERS, "Content-Type": "application/json"},
                          timeout=TIMEOUT)
        if r.status_code == 200:
            return r.json().get("total", 0)
    except requests.RequestException:
        return None
    return 0


def audit_simple(name, slugs, probe):
    print(f"\n{'='*60}\n{name}  ({len(slugs)} slugs)\n{'='*60}")
    alive, dead = [], []
    for slug in slugs:
        n = probe(slug)
        if n:
            alive.append((slug, n))
        else:
            dead.append(slug)
        time.sleep(0.1)
    print(f"  ALIVE: {len(alive)}   DEAD: {len(dead)}")
    if dead:
        print(f"  ❌ dead slugs to remove:\n     " + ", ".join(dead))
    return alive, dead


def audit_smartrecruiters():
    print(f"\n{'='*60}\nsmartrecruiters  ({len(smartrecruiters.COMPANIES)} slugs)\n{'='*60}")
    alive, dead = [], []
    for disp, slug in smartrecruiters.COMPANIES:
        n = probe_smartrecruiters(slug)
        if n:
            alive.append((slug, n))
        else:
            dead.append(f"{disp}:{slug}")
        time.sleep(0.1)
    print(f"  ALIVE: {len(alive)}   DEAD: {len(dead)}")
    if dead:
        print(f"  ❌ dead: " + ", ".join(dead))
    return alive, dead


def audit_workday():
    print(f"\n{'='*60}\nworkday  ({len(workday.COMPANIES)} slugs)\n{'='*60}")
    alive, dead = [], []
    for disp, tenant, ver, board in workday.COMPANIES:
        n = probe_workday(tenant, ver, board)
        if n:
            alive.append((disp, n))
        else:
            dead.append(disp)
        time.sleep(0.1)
    print(f"  ALIVE: {len(alive)}   DEAD: {len(dead)}")
    if alive:
        print(f"  ✅ working: " + ", ".join(f"{d}({n})" for d, n in alive))
    if dead:
        print(f"  ❌ dead: " + ", ".join(dead))
    return alive, dead


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    summary = {}
    if which in ("all", "greenhouse"):
        summary["greenhouse"] = audit_simple("greenhouse", greenhouse.COMPANIES, probe_greenhouse)
    if which in ("all", "lever"):
        summary["lever"] = audit_simple("lever", lever.COMPANIES, probe_lever)
    if which in ("all", "ashby"):
        summary["ashby"] = audit_simple("ashby", ashby.COMPANIES, probe_ashby)
    if which in ("all", "smartrecruiters"):
        summary["smartrecruiters"] = audit_smartrecruiters()
    if which in ("all", "workday"):
        summary["workday"] = audit_workday()

    print(f"\n{'#'*60}\n# SUMMARY\n{'#'*60}")
    for plat, (alive, dead) in summary.items():
        print(f"  {plat:<18} alive={len(alive):>3}  dead={len(dead):>3}")


if __name__ == "__main__":
    main()
