import re
from datetime import datetime, timezone, date
import pytz

IST = pytz.timezone("Asia/Kolkata")

# ── Location helpers ──────────────────────────────────────────────────────────

INDIA_LOCATION_KEYWORDS = {
    "india", "bangalore", "bengaluru", "mumbai", "pune", "hyderabad",
    "chennai", "delhi", "new delhi", "noida", "gurgaon", "gurugram",
    "kolkata", "ahmedabad", "jaipur", "kochi", "trivandrum", "coimbatore",
    "chandigarh", "indore", "bhopal", "nagpur", "surat", "vizag",
    "visakhapatnam", "lucknow", "patna", "bhubaneswar", "remote",
    "worldwide", "global", "anywhere", "work from home", "wfh",
}

REMOTE_LOCATION_KEYWORDS = {"remote", "worldwide", "global", "anywhere", "work from home", "wfh", "flexible"}

NON_INDIA_COUNTRIES = {
    "uk", "united kingdom", "gb", "usa", "united states", "us",
    "australia", "au", "canada", "ca", "europe", "germany", "de",
    "france", "fr", "netherlands", "nl", "singapore", "sg",
    "uae", "united arab emirates", "ae", "brazil", "br",
    "japan", "jp", "china", "cn", "south korea", "kr",
    "mexico", "mx", "spain", "es", "italy", "it", "poland", "pl",
    "sweden", "se", "norway", "no", "denmark", "dk", "finland", "fi",
    "switzerland", "ch", "austria", "at", "belgium", "be",
    "new zealand", "nz", "ireland", "ie", "portugal", "pt",
    "argentina", "ar", "colombia", "co", "chile", "cl",
}

NON_INDIA_LOCATION_KEYWORDS = {
    "london", "berlin", "paris", "amsterdam", "toronto", "sydney",
    "new york", "san francisco", "los angeles", "chicago", "seattle",
    "boston", "austin", "denver", "atlanta", "miami", "dallas",
    "washington", "philadelphia", "phoenix", "portland",
    "germany", "france", "netherlands", "canada", "australia",
    "united states", "united kingdom", "eu only", "europe only",
    "hong kong", "beijing", "shanghai", "tokyo", "seoul",
    "amsterdam", "stockholm", "oslo", "copenhagen", "helsinki",
    "zurich", "vienna", "warsaw", "lisbon", "madrid", "barcelona",
    "milan", "rome", "dublin", "edinburgh", "manchester",
}


def is_india_or_remote(country: str, location: str) -> bool:
    """Returns True if job is India-based or remote/worldwide."""
    country_l = (country or "").lower().strip()
    location_l = (location or "").lower()

    if country_l in ("india", "in"):
        return True
    if country_l in ("remote", "worldwide", "global", ""):
        pass  # need location check
    elif country_l in NON_INDIA_COUNTRIES:
        return False

    # Check location for India/remote keywords
    if any(kw in location_l for kw in INDIA_LOCATION_KEYWORDS):
        return True
    if any(kw in location_l for kw in NON_INDIA_LOCATION_KEYWORDS):
        return False

    return True  # unknown → include


def is_english(title: str, description: str = "") -> bool:
    """Returns True if text is likely in English (or indeterminate)."""
    text = f"{title} {description[:400]}"
    if not text.strip():
        return True
    # Detect non-Latin script blocks (CJK, Arabic, Cyrillic, Korean, Devanagari)
    NON_ENGLISH_RANGES = [
        (0x0400, 0x04FF),   # Cyrillic
        (0x0600, 0x06FF),   # Arabic
        (0x0900, 0x097F),   # Devanagari (Hindi script)
        (0x3040, 0x30FF),   # Japanese
        (0x4E00, 0x9FFF),   # CJK (Chinese/Japanese)
        (0xAC00, 0xD7AF),   # Korean
        (0x0E00, 0x0E7F),   # Thai
        (0x0370, 0x03FF),   # Greek
    ]
    non_english = sum(
        1 for c in text
        if any(lo <= ord(c) <= hi for lo, hi in NON_ENGLISH_RANGES)
    )
    if non_english > 5:
        return False
    # Check for German/French keyword patterns
    de_words = re.findall(r'\b(und|oder|für|mit|die|der|das|ist|wir|werden|haben|eine|seinen|ihrer|unserer|Kenntnisse|Erfahrung)\b', text)
    fr_words = re.findall(r'\b(et|ou|les|des|une|avec|vous|nous|est|sont|dans|pour|nous|votre|notre|équipe)\b', text)
    if len(de_words) >= 3 or len(fr_words) >= 3:
        return False
    return True


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

def build_description(
    raw: str,
    responsibilities: str = "",
    requirements: str = "",
    skills: str = "",
    about_company: str = "",
    salary: str = "",
    job_type: str = "",
    location: str = "",
) -> str:
    """Build a clean, structured job description in English."""
    parts = []

    # Intro / overview
    raw_text = clean_html(raw).strip() if raw else ""
    if raw_text:
        # If text already contains structured sections, keep as-is
        if any(marker in raw_text.lower() for marker in
               ["responsibilities", "requirements", "qualifications", "about the role", "what you'll do"]):
            parts.append(raw_text[:4000])
        else:
            parts.append(raw_text[:2000])

    def _add_section(heading: str, content: str):
        content = content.strip()
        if content and content not in ("Not Specified", "N/A", "-", ""):
            parts.append(f"**{heading}**\n{content}")

    _add_section("Key Responsibilities", responsibilities)
    _add_section("Requirements & Qualifications", requirements)
    _add_section("Skills", skills)

    # Metadata footer
    meta = []
    if location and location not in ("Not Specified",):
        meta.append(f"Location: {location}")
    if job_type and job_type not in ("Not Specified",):
        meta.append(f"Job Type: {job_type}")
    if salary and salary not in ("Not Disclosed", "Not Specified"):
        meta.append(f"Salary: {salary}")
    if meta:
        parts.append("\n".join(meta))

    text = "\n\n".join(parts).strip()
    return text[:5000] if text else "No description available."

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


def normalize_work_mode(location: str, job_type: str = "") -> str:
    """Extract Remote / Hybrid / On-site from location and job type."""
    loc = (location or "").lower()
    jt = (job_type or "").lower()
    combined = f"{loc} {jt}"
    if "hybrid" in combined:
        return "Hybrid"
    if any(w in combined for w in ["remote", "work from home", "wfh", "worldwide", "anywhere", "global"]):
        return "Remote"
    return "On-site"


def extract_education(text: str) -> str:
    """Extract education requirement from job description text."""
    if not text:
        return "Not Specified"
    t = text.lower()
    PATTERNS = [
        (r"\bphd\b|\bdoctorate\b|\bd\.?phil\b", "PhD"),
        (r"\bm\.?tech\b|\bm\.?e\.?\b|\bmaster.{0,20}(tech|engineer)", "M.Tech / M.E."),
        (r"\bmba\b|\bmaster.{0,15}business", "MBA"),
        (r"\bmsc\b|\bm\.?sc\.?\b|\bmaster.{0,15}science", "M.Sc."),
        (r"\bmca\b|\bmaster.{0,20}computer", "MCA"),
        (r"\bm\.?s\b|\bmaster.{0,10}(science|arts|engineering)\b", "Master's Degree"),
        (r"\bb\.?tech\b|\bb\.?e\.?\b|\bbachelor.{0,20}(tech|engineer)", "B.Tech / B.E."),
        (r"\bbca\b|\bbachelor.{0,20}computer application", "BCA"),
        (r"\bbsc\b|\bb\.?sc\.?\b|\bbachelor.{0,15}science", "B.Sc."),
        (r"\bbba\b|\bbachelor.{0,15}(business|commerce)", "BBA / B.Com"),
        (r"\bany\s+graduate\b|\bany\s+degree\b|\bgraduat", "Any Graduate"),
        (r"\bpostgraduate\b|\bpost.?grad", "Post Graduate"),
        (r"\bdiploma\b", "Diploma"),
    ]
    for pattern, label in PATTERNS:
        if re.search(pattern, t):
            return label
    return "Not Specified"


def infer_functional_area(title: str, category: str = "", description: str = "") -> str:
    """Infer functional area / department from job title and category."""
    text = f"{title} {category} {description[:100]}".lower()
    if re.search(r"\bmachine.?learning\b|\bml.?engineer\b|\bai.?engineer\b|\bdeep.?learning\b|\bllm\b|\bgen.?ai\b", text):
        return "AI / Machine Learning"
    if re.search(r"\bdata.?scientist\b|\bdata.?analyst\b|\banalytic\b|\bbi.?developer\b|\bbusiness.?intelligence\b", text):
        return "Data & Analytics"
    if re.search(r"\bdata.?engineer\b|\betl\b|\bspark\b|\bkafka\b|\bairflow\b|\bdatabrick\b", text):
        return "Data Engineering"
    if re.search(r"\bdevops\b|\bsre\b|\bsite.?reliability\b|\binfrastructure\b|\bplatform.?engineer\b", text):
        return "DevOps & Infrastructure"
    if re.search(r"\bcloud.?engineer\b|\baws.?engineer\b|\bazure.?engineer\b|\bgcp\b", text):
        return "Cloud Engineering"
    if re.search(r"\bmobile\b|\bandroid\b|\bios\b|\bflutter\b|\breact.?native\b|\bswift\b|\bkotlin\b", text):
        return "Mobile Development"
    if re.search(r"\bfrontend\b|\bfront.?end\b|\bui.?developer\b|\breact\b|\bangular\b|\bvue\b", text):
        return "Frontend Development"
    if re.search(r"\bbackend\b|\bback.?end\b|\bnode\.?js\b|\bdjango\b|\bspring\b|\brails\b|\bapi\b", text):
        return "Backend Development"
    if re.search(r"\bfull.?stack\b", text):
        return "Full Stack Development"
    if re.search(r"\bqa\b|\bquality.?assurance\b|\btester\b|\btest.?engineer\b|\bsdet\b|\bautomation.?test\b", text):
        return "Quality Assurance"
    if re.search(r"\bsecurity\b|\bcybersecur\b|\binfosec\b|\bpenetration\b|\bdevsecops\b", text):
        return "Cybersecurity"
    if re.search(r"\bproduct.?manager\b|\bproduct.?owner\b|\bpm\b|\bprogram.?manager\b", text):
        return "Product Management"
    if re.search(r"\bdesigner\b|\bux\b|\bui/ux\b|\binteraction.?design\b|\bvisual.?design\b", text):
        return "Design"
    if re.search(r"\btech.?lead\b|\beng.*?manager\b|\bstaff.?eng\b|\bprincipal.?eng\b|\bvp.?eng\b|\bdirector.?eng\b", text):
        return "Engineering Leadership"
    if re.search(r"\bdba\b|\bdatabase.?admin\b|\bsql.?admin\b|\bpostgres\b", text):
        return "Database Administration"
    if re.search(r"\bsap\b|\berp\b|\boracle.?dba\b|\bsalesforce\b|\bcrm\b", text):
        return "ERP / CRM"
    if re.search(r"\bengineer\b|\bdeveloper\b|\bprogrammer\b|\bcoder\b|\bsde\b|\bswe\b", text):
        return "Software Engineering"
    return "Information Technology"


def infer_industry(company: str, category: str = "", title: str = "") -> str:
    """Infer industry sector from company name, category and job title."""
    text = f"{company} {category} {title}".lower()
    if re.search(r"\bfintech\b|\bbank\b|\bfinance\b|\bpayment\b|\binsur\b|\blend\b|\binvest\b|\btrading\b|\bwealth\b|\bstock\b|\bnbfc\b|\bneobank\b", text):
        return "Fintech / Finance"
    if re.search(r"\bhealth\b|\bpharma\b|\bmedical\b|\bhospital\b|\bclinic\b|\bhealthcare\b|\bdiagnostic\b", text):
        return "Healthcare & Pharma"
    if re.search(r"\bedtech\b|\beducation\b|\blearning\b|\bschool\b|\buniversit\b|\bcourse\b|\btutor\b|\bcoach\b", text):
        return "EdTech / Education"
    if re.search(r"\becomm\b|\be-comm\b|\bretail\b|\bshopping\b|\bmarketplace\b|\bfashion\b|\bbeauty\b", text):
        return "E-commerce / Retail"
    if re.search(r"\blogistic\b|\bdelivery\b|\bshipping\b|\btransport\b|\bsupply.?chain\b|\bwarehouse\b|\bfreight\b", text):
        return "Logistics & Supply Chain"
    if re.search(r"\bgaming\b|\bgame\b|\besport\b", text):
        return "Gaming"
    if re.search(r"\bmedia\b|\bcontent\b|\bnews\b|\bpublish\b|\bott\b|\bstream\b|\bpodcast\b", text):
        return "Media & Content"
    if re.search(r"\btravel\b|\bhospitalit\b|\bhotel\b|\btourism\b|\bairline\b|\bflight\b", text):
        return "Travel & Hospitality"
    if re.search(r"\breal.?estate\b|\bproptech\b|\bproperty\b|\bhome.?loan\b", text):
        return "Real Estate / PropTech"
    if re.search(r"\bagritech\b|\bagriculture\b|\bfarm\b|\bfood.?tech\b|\bfmcg\b", text):
        return "AgriTech / FoodTech"
    if re.search(r"\bhr.?tech\b|\bhrms\b|\brecruit\b|\btalent\b", text):
        return "HR Tech"
    if re.search(r"\bev\b|\belectric.?vehicle\b|\bautotech\b|\bautomotive\b", text):
        return "Automotive / EV"
    if re.search(r"\bsaas\b|\bsoftware\b|\bcloud\b|\bplatform\b|\bdev.?tools\b|\binfosys\b|\bwipro\b|\btcs\b|\bhcl\b|\bcognizant\b|\btech.?mahindra\b|\baccenture\b|\bcapgemini\b", text):
        return "IT Services / SaaS"
    if re.search(r"\bai\b|\bml\b|\bmachine.?learning\b|\bartificial.?intel\b", text):
        return "AI / ML"
    return "Information Technology"


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
