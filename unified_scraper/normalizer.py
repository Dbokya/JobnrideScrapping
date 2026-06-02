import re
from datetime import datetime, timezone, date
import pytz

IST = pytz.timezone("Asia/Kolkata")


def today_ist() -> date:
    return datetime.now(IST).date()


def is_posted_today(raw_date) -> bool:
    """
    Returns True if raw_date (str, int ms, or datetime) is today in IST.
    Accepts: ISO string, Unix timestamp (int/float), datetime object.
    Returns True if raw_date is None/empty so we don't drop jobs with no date.
    """
    if raw_date is None or raw_date == "":
        return True  # no date info → include it (don't drop unknowns)
    try:
        today = today_ist()

        if isinstance(raw_date, (int, float)):
            # Unix timestamp in milliseconds or seconds
            ts = raw_date / 1000 if raw_date > 1e10 else raw_date
            dt = datetime.fromtimestamp(ts, tz=timezone.utc).astimezone(IST)
            return dt.date() == today

        if isinstance(raw_date, datetime):
            if raw_date.tzinfo is None:
                raw_date = pytz.utc.localize(raw_date)
            return raw_date.astimezone(IST).date() == today

        if isinstance(raw_date, str):
            s = raw_date.strip()
            if not s or s.lower() in ["null", "none", "n/a"]:
                return True
            # Handle "2 days ago", "Today", "Just now" style strings
            sl = s.lower()
            if any(w in sl for w in ["today", "just now", "an hour", "hours ago", "minutes ago", "minute ago"]):
                return True
            if "yesterday" in sl or "days ago" in sl or "week" in sl:
                return False
            # Try parsing ISO / common date formats
            for fmt in [
                "%Y-%m-%dT%H:%M:%S.%fZ",
                "%Y-%m-%dT%H:%M:%SZ",
                "%Y-%m-%dT%H:%M:%S%z",
                "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d",
                "%d/%m/%Y",
                "%m/%d/%Y",
                "%B %d, %Y",
                "%d %B %Y",
            ]:
                try:
                    dt = datetime.strptime(s[:26], fmt)
                    if dt.tzinfo is None:
                        dt = pytz.utc.localize(dt)
                    return dt.astimezone(IST).date() == today
                except ValueError:
                    continue
            # If we can't parse it, include the job
            return True
    except Exception:
        return True  # parsing failed → include the job
    return True

def normalize_experience(text: str) -> str:
    if not text:
        return "Not Specified"
    t = text.lower().strip()
    if any(w in t for w in ["fresher", "entry level", "0 year", "no experience", "student", "graduate"]):
        return "0-2 years"
    if any(w in t for w in ["intern", "internship"]):
        return "0-2 years"

    t = t.replace("–", "-").replace("—", "-")
    t = re.sub(r"\bto\b", "-", t)
    t = re.sub(r"years?|yrs?|experience|exp\.?", "", t)
    t = re.sub(r"[^0-9\-]", " ", t).strip()
    numbers = [int(n) for n in re.findall(r"\d+", t)]

    if not numbers:
        return "Not Specified"

    top = max(numbers)
    bot = min(numbers)

    if top <= 2:
        return "0-2 years"
    if top <= 5:
        return "0-2 years" if bot <= 1 else "2-5 years"
    if top <= 10:
        return "2-5 years" if bot <= 2 else "5-10 years"
    return "10+ years"

def normalize_job_type(text: str) -> str:
    if not text:
        return "Full-Time"
    t = text.lower()
    if "intern" in t:
        return "Internship"
    if "part" in t:
        return "Part-Time"
    if "contract" in t or "freelance" in t or "freelancing" in t:
        return "Contract"
    if "remote" in t:
        return "Remote"
    return "Full-Time"

def classify_job_for(title: str, description: str) -> str:
    text = f"{title} {description}".lower()
    if re.search(r"\bintern(ship)?\b", text):
        return "intern"
    if re.search(r"\b(fresher|entry.?level|junior|graduate|trainee)\b", text):
        return "fresher"
    return "experienced"

def clean_html(html: str) -> str:
    if not html:
        return ""
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    text = re.sub(r"&quot;", '"', text)
    text = re.sub(r"\s+", " ", text).strip()
    return text

def normalize_location(location: str) -> str:
    if not location:
        return "Not Specified"
    # Clean up excessive whitespace / commas
    loc = re.sub(r"\s+", " ", location).strip()
    loc = re.sub(r",\s*,", ",", loc)
    return loc[:200]  # cap length

def normalize_salary(salary: str) -> str:
    if not salary:
        return "Not Disclosed"
    s = salary.strip()
    if not s or s.lower() in ["null", "none", "n/a", "na", "0", "-"]:
        return "Not Disclosed"
    return s

def build_description(raw: str, responsibilities: str = "", requirements: str = "") -> str:
    parts = []
    if raw:
        parts.append(clean_html(raw))
    if responsibilities and responsibilities not in ["Not Specified", ""]:
        parts.append(f"Responsibilities: {responsibilities}")
    if requirements and requirements not in ["Not Specified", ""]:
        parts.append(f"Requirements: {requirements}")
    text = "\n\n".join(parts).strip()
    return text[:3000] if text else "No description available."

IT_KEYWORDS = {
    # Roles
    "software", "developer", "engineer", "programmer", "coder",
    "devops", "sre", "devsecops", "architect", "fullstack", "full stack",
    "frontend", "front end", "backend", "back end", "mobile", "android", "ios",
    "cloud", "data", "ml", "ai", "machine learning", "deep learning",
    "data science", "data engineer", "data analyst", "bi developer",
    "qa", "quality assurance", "automation", "test engineer", "sdet",
    "product manager", "product owner", "scrum", "agile",
    "cybersecurity", "security engineer", "penetration", "infosec",
    "network engineer", "system admin", "sysadmin", "infrastructure",
    "database", "dba", "sql", "nosql", "mongodb", "postgresql",
    "technical lead", "tech lead", "engineering manager",
    "solution architect", "enterprise architect",
    "ui/ux", "ux designer", "ui designer", "interaction design",
    "erp", "sap", "oracle", "salesforce", "crm",
    "blockchain", "web3", "smart contract",
    # Technologies
    "python", "java", "javascript", "typescript", "golang", "go lang",
    "react", "angular", "vue", "node.js", "nodejs", "django", "flask",
    "spring", "kubernetes", "docker", "aws", "azure", "gcp",
    "terraform", "ansible", "jenkins", "ci/cd",
    "hadoop", "spark", "kafka", "airflow", "databricks",
    "tensorflow", "pytorch", "scikit", "pandas", "numpy",
    "ios", "swift", "kotlin", "flutter", "react native",
    "php", "ruby", "scala", "rust", "c++", "c#", ".net",
    "mysql", "redis", "elasticsearch", "cassandra",
    "microservices", "rest api", "graphql",
    "it support", "helpdesk", "technical support",
}

def is_it_job(title: str, description: str = "", category: str = "") -> bool:
    """Returns True if the job is IT/tech related."""
    text = f"{title} {description[:300]} {category}".lower()
    return any(kw in text for kw in IT_KEYWORDS)


def normalize_skills(skills) -> str:
    if not skills:
        return "Not Specified"
    if isinstance(skills, list):
        cleaned = [s.strip() for s in skills if s and len(s.strip()) > 1]
        return ", ".join(cleaned)
    s = str(skills)
    s = re.sub(r";", ",", s)
    s = re.sub(r",\s*", ", ", s)
    return s.strip() or "Not Specified"
