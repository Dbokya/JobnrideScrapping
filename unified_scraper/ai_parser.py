"""
ai_parser.py — Two-phase job description section extractor.

Phase 1 (free): BeautifulSoup HTML structure parsing — handles ~65% of jobs
                that have proper headings (<h2>, <strong>, etc.)

Phase 2 (~$0.001/call): GPT-4o mini fallback for plain-text / unstructured
                         descriptions where Phase 1 finds nothing useful.

Usage:
    from ai_parser import parse_job_sections
    sections = parse_job_sections(raw_html="...", plain_text="...")
    # sections keys: responsibilities, requirements, benefits, aboutCompany, salary
"""

import os
import re
import json

from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Section heading keyword maps
# ---------------------------------------------------------------------------

_SECTION_KEYWORDS: dict[str, list[str]] = {
    "responsibilities": [
        "responsibilities", "what you'll do", "what you will do", "your role",
        "key duties", "job duties", "day to day", "about the role", "the role",
        "what you'd do", "you will", "key responsibilities", "role overview",
        "position overview", "your day", "in this role", "what we expect",
        "your responsibilities", "primary responsibilities", "core responsibilities",
    ],
    "requirements": [
        "requirements", "qualifications", "what you'll need", "what we're looking for",
        "skills required", "must have", "minimum qualifications", "preferred qualifications",
        "basic qualifications", "required skills", "you have", "you bring",
        "who you are", "what you have", "experience required", "required experience",
        "desired skills", "technical skills", "about you", "ideal candidate",
        "what you need", "skills & experience", "key skills",
    ],
    "benefits": [
        "benefits", "perks", "what we offer", "compensation", "why join",
        "why us", "life at", "what you get", "our offer", "we offer",
        "total rewards", "our benefits", "employee benefits", "what's in it for you",
    ],
    "aboutCompany": [
        "about us", "about the company", "who we are", "our company",
        "company overview", "our mission", "the company", "about jobnride",
    ],
}


def _match_section(heading_text: str) -> str | None:
    """Return section key if heading matches a known section, else None."""
    h = heading_text.lower().strip()
    # Skip very long strings — not a section heading
    if len(h) > 80:
        return None
    for section, keywords in _SECTION_KEYWORDS.items():
        if any(kw in h for kw in keywords):
            return section
    return None


# ---------------------------------------------------------------------------
# Phase 1 — HTML structure parsing
# ---------------------------------------------------------------------------

def parse_sections_from_html(html: str) -> dict:
    """
    Parse job posting HTML using BeautifulSoup to extract structured sections.

    Looks for heading tags (h1-h4) and bold/strong tags that match known
    section keywords, then collects the content that follows each heading
    until the next heading is found.

    Returns a dict with any found sections. Returns empty dict if no
    recognisable sections are found (triggers Phase 2 fallback).
    """
    if not html or len(html.strip()) < 100:
        return {}

    try:
        soup = BeautifulSoup(html, "html.parser")
    except Exception:
        return {}

    result: dict[str, str] = {}

    # All tags that could be section headings
    heading_tags = soup.find_all(["h1", "h2", "h3", "h4", "strong", "b"])

    for heading in heading_tags:
        heading_text = heading.get_text(strip=True)
        section_key = _match_section(heading_text)
        if not section_key or section_key in result:
            continue

        content_parts: list[str] = []

        for sibling in heading.find_next_siblings():
            # Stop at the next heading
            if sibling.name in ("h1", "h2", "h3", "h4"):
                break
            if sibling.name in ("strong", "b"):
                sib_text = sibling.get_text(strip=True)
                if _match_section(sib_text):
                    break

            if sibling.name in ("ul", "ol"):
                for li in sibling.find_all("li"):
                    text = li.get_text(separator=" ", strip=True)
                    if text:
                        content_parts.append(f"• {text}")
            elif sibling.name == "p":
                text = sibling.get_text(separator=" ", strip=True)
                if text:
                    content_parts.append(text)
            else:
                text = sibling.get_text(separator=" ", strip=True)
                if text and len(text) > 5:
                    content_parts.append(text)

        content = "\n".join(p for p in content_parts if p.strip()).strip()
        if content and len(content) > 20:
            result[section_key] = content[:3000]

    return result  # empty dict → triggers Phase 2


# ---------------------------------------------------------------------------
# Phase 2 — GPT-4o mini fallback
# ---------------------------------------------------------------------------

_openai_client = None


def _get_openai_client():
    global _openai_client
    if _openai_client is not None:
        return _openai_client
    try:
        from openai import OpenAI
        key = os.environ.get("OPENAI_API_KEY", "")
        if not key:
            print("  ⚠ OPENAI_API_KEY not set — GPT fallback disabled")
            return None
        _openai_client = OpenAI(api_key=key)
        return _openai_client
    except ImportError:
        print("  ⚠ openai package not installed — GPT fallback disabled")
        return None


_GPT_PROMPT = """\
Extract structured information from this job posting. Return ONLY valid JSON, no markdown, no explanation.

JSON keys (use empty string "" if not found):
- "description": 2-3 sentence summary of the role and company. Do NOT include responsibilities or requirements here. Plain text only.
- "responsibilities": bullet list of what the person will do, each item on its own line starting with "• ". Plain text only.
- "requirements": bullet list of what skills/experience are needed, each item on its own line starting with "• ". Plain text only.
- "benefits": comma-separated list of perks/benefits (e.g. "Health insurance, flexible hours, stock options")
- "aboutCompany": 1-2 sentences describing the company. Plain text only.
- "salary": exact salary or range if mentioned anywhere in the text (e.g. "15-20 LPA", "₹12-18 LPA", "$80k-$100k", "Competitive"). Empty string if not found.
- "experience": years of experience required as a range string (e.g. "2-5 years", "5+ years", "0-2 years", "Fresher"). Empty string if not found.
- "skills": comma-separated list of specific technical skills mentioned (e.g. "Python, AWS, Docker, PostgreSQL")

Job posting text:
"""


def _call_gpt(plain_text: str) -> dict:
    """Call GPT-4o mini to extract all structured fields. Returns {} on failure."""
    client = _get_openai_client()
    if not client:
        return {}

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": _GPT_PROMPT + plain_text[:4000]}],
            temperature=0,
            max_tokens=1200,
            response_format={"type": "json_object"},
        )
        raw = response.choices[0].message.content or "{}"
        return json.loads(raw)
    except Exception as e:
        print(f"  ⚠ GPT-4o mini error: {e}")
        return {}


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def parse_job_sections(raw_html: str = "", plain_text: str = "") -> dict:
    """
    Combined Phase 1 + GPT extractor.

    Phase 1 (free):      BeautifulSoup HTML parsing — extracts responsibilities
                         and requirements from heading structure when available.

    GPT-4o mini (~$0.001): Always called when plain_text is available to extract
                            description summary, salary, experience, skills, and
                            fill any gaps Phase 1 missed.

    Args:
        raw_html:   Raw HTML from the scraper (before clean_html destroys it).
        plain_text: Already-cleaned plain text description.

    Returns:
        dict with populated fields:
          description, responsibilities, requirements, benefits,
          aboutCompany, salary, experience, skills
    """
    sections: dict[str, str] = {}

    # ── Phase 1: HTML structure parsing (free) ───────────────────────────────
    if raw_html:
        sections = parse_sections_from_html(raw_html)

    # ── GPT-4o mini: always run for salary/experience/description/skills ─────
    if plain_text and len(plain_text.strip()) > 150:
        print("  🤖 GPT-4o mini extracting fields...")
        ai = _call_gpt(plain_text)

        # GPT fills salary, experience, skills, description always
        # For responsibilities/requirements, only fill if Phase 1 missed them
        for key in ("salary", "experience", "skills", "description", "benefits", "aboutCompany"):
            val = (ai.get(key) or "").strip()
            if val:
                sections[key] = val

        # Phase 1 results take priority for responsibilities/requirements
        for key in ("responsibilities", "requirements"):
            if not sections.get(key):
                val = (ai.get(key) or "").strip()
                if val:
                    sections[key] = val

    return sections


# ---------------------------------------------------------------------------
# Quick smoke test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    sample_html = """
    <div>
      <h2>About the Role</h2>
      <p>We are building the next generation payment platform.</p>
      <h2>Responsibilities</h2>
      <ul>
        <li>Design and implement scalable backend services</li>
        <li>Collaborate with frontend engineers</li>
        <li>Write clean, tested, documented code</li>
      </ul>
      <h2>Requirements</h2>
      <ul>
        <li>3+ years of Python or Go experience</li>
        <li>Experience with distributed systems</li>
        <li>Strong SQL fundamentals</li>
      </ul>
      <h2>Benefits</h2>
      <p>Health insurance, flexible hours, remote-friendly, stock options</p>
    </div>
    """
    result = parse_job_sections(raw_html=sample_html)
    for k, v in result.items():
        print(f"\n--- {k} ---\n{v}")
