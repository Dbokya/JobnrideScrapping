import requests
import re
import pytz
import json
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import firebase_admin
from firebase_admin import credentials, firestore, messaging
import os
import time
import openai
import sys
import requests as _requests_existence_check

# ------------------ FIREBASE INIT ------------------
cred = credentials.Certificate("serviceaccount/jobnride-97d77-firebase-adminsdk-fbsvc-20ce6e6129.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

# ------------------ OPENAI INIT ------------------
OPENAI_API_KEY = os.getenv("OPEN_AI_API_KEY", "").strip()
SKIP_AI = os.getenv("SKIP_AI", "false").lower() in ("1", "true", "yes")
if not OPENAI_API_KEY:
    SKIP_AI = True
    print("⚠ OPEN_AI_API_KEY not set — running in SKIP_AI mode (table extraction only)")

# openai v1.x client
_openai_client = openai.OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

# Allow overriding the OpenAI model via env var.
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")

# ------------------ CONFIG ------------------
BASE_API = "https://jobcode.in/wp-json/wp/v2/posts?per_page=100&page="
IST = pytz.timezone("Asia/Kolkata")

# ------------------ HELPER FUNCTIONS ------------------

def fetch_jobs_page(page, retries=5, backoff_factor=1, timeout=10):
    """Fetch jobs page JSON with retries and exponential backoff.

    Returns:
      - list (possibly empty) on success
      - empty list if page exists but returns non-200
      - None on persistent network failure (caller should handle exit)
    """
    url = BASE_API + str(page)
    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(url, timeout=timeout, headers={"User-Agent": "JobNRideBot/1.0"})
            if resp.status_code != 200:
                print(f"⚠ HTTP {resp.status_code} when fetching page {page}")
                return []
            return resp.json()
        except requests.exceptions.RequestException as e:
            # Network-related error, retry with exponential backoff
            wait = backoff_factor * (2 ** (attempt - 1))
            print(f"⚠ Network error fetching {url}: {e} (attempt {attempt}/{retries}). Retrying in {wait}s...")
            time.sleep(wait)

    # All retries exhausted — indicate persistent network failure
    print(f"❌ Failed to fetch {url} after {retries} attempts. Network may be unreachable.")
    return None

def fetch_featured_image_url(media_id, retries=3):
    """Fetch the actual image URL from WordPress media ID"""
    if not media_id:
        return None
    
    media_url = f"https://jobcode.in/wp-json/wp/v2/media/{media_id}"
    
    for attempt in range(retries):
        try:
            resp = requests.get(media_url, timeout=10, headers={"User-Agent": "JobNRideBot/1.0"})
            if resp.status_code == 200:
                media_data = resp.json()
                # Get the full size image URL
                image_url = media_data.get("source_url")
                if image_url:
                    print(f"✓ Found featured image: {image_url}")
                    return image_url
        except Exception as e:
            print(f"⚠ Error fetching media {media_id}: {e}")
            if attempt < retries - 1:
                time.sleep(1)
    
    return None

def classify_job(title, content):
    text = f"{title} {content}".lower()
    if re.search(r"\bintern(ship)?\b", text):
        return "intern"
    if re.search(r"\b(fresher|entry level|junior)\b", text):
        return "fresher"
    return "experienced"

def normalize_experience(experience_text):
    """Normalize experience to standard year ranges: 0-2, 2-5, 5-10, 10+"""
    if not experience_text or experience_text.lower() in ["not specified", "n/a", "na"]:
        return "Not Specified"

    # Normalize common unicode/human formats and remove noise
    text = str(experience_text).lower()
    # replace unicode dashes with ascii
    text = text.replace('\u2013', '-').replace('\u2014', '-')
    # common separators like 'to', '–', '—', '–'
    text = re.sub(r'\bto\b', '-', text)
    # remove words and punctuation that are irrelevant
    text = re.sub(r'years?|yrs?|year[s]?|experience|exp\.?', '', text)
    text = re.sub(r'[^0-9\-\s]', ' ', text)
    text = text.replace(' ', '')

    # Handle freshers explicitly
    if any(word in experience_text.lower() for word in ["fresher", "freshers", "no experience", "entry level", "student", "students"]):
        return "0-2 years"

    # Extract numbers from cleaned text
    numbers = re.findall(r'\d+', text)
    if not numbers:
        # As a last resort, return standardized Not Specified
        return "Not Specified"

    numbers = [int(n) for n in numbers]
    
    # If only one number found
    if len(numbers) == 1:
        num = numbers[0]
        if num == 0:
            return "0-2 years"
        elif num <= 2:
            return "0-2 years"
        elif num <= 5:
            return "2-5 years"
        elif num <= 10:
            return "5-10 years"
        else:
            return "10+ years"
    
    # If two or more numbers found (range given)
    min_exp = min(numbers)
    max_exp = max(numbers)
    
    if max_exp <= 2:
        return "0-2 years"
    elif max_exp <= 5:
        if min_exp <= 2:
            return "0-2 years" if max_exp <= 2 else "2-5 years"
        return "2-5 years"
    elif max_exp <= 10:
        if min_exp <= 2:
            return "2-5 years"
        elif min_exp <= 5:
            return "5-10 years"
        return "5-10 years"
    else:
        return "10+ years"

def extract_apply_link(html):
    soup = BeautifulSoup(html, "html.parser")
    apply_button = soup.find("a", string=re.compile("Apply", re.IGNORECASE))
    if apply_button and apply_button.get("href"):
        return apply_button["href"]
    return ""


def fetch_url_html(url, timeout=10):
    """Fetch HTML of a URL, return None on failure"""
    try:
        if not url:
            return None
        resp = requests.get(url, timeout=timeout, headers={"User-Agent": "JobNRideBot/1.0"})
        if resp.status_code == 200:
            return resp.text
        print(f"⚠ Failed to fetch apply page {url}: HTTP {resp.status_code}")
    except Exception as e:
        print(f"⚠ Exception fetching apply page {url}: {e}")
    return None

def extract_company_from_url(url):
    """Extract company name from apply link URL."""
    if not url:
        return None
    
    try:
        # Common job board patterns
        patterns = [
            r'greenhouse\.io/([^/]+)',           # greenhouse.io/companyname
            r'jobs\.lever\.co/([^/]+)',          # jobs.lever.co/companyname
            r'apply\.workable\.com/([^/]+)',     # apply.workable.com/companyname
            r'boards\.greenhouse\.io/([^/]+)',   # boards.greenhouse.io/companyname
            r'careers\.([^./]+)\.',              # careers.companyname.com
            r'jobs\.([^./]+)\.',                 # jobs.companyname.com
            r'//([^./]+)\.com/careers',          # companyname.com/careers
            r'//([^./]+)\.com/jobs',             # companyname.com/jobs
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url, re.IGNORECASE)
            if match:
                company = match.group(1)
                # Clean up the company name
                company = company.replace('-', ' ').replace('_', ' ')
                # Capitalize each word
                company = ' '.join(word.capitalize() for word in company.split())
                return company
        
        # Try to extract from domain as fallback
        domain_match = re.search(r'//(?:www\.)?([^./]+)', url)
        if domain_match:
            domain = domain_match.group(1)
            # Skip common job board domains
            job_boards = ['greenhouse', 'lever', 'workable', 'indeed', 'linkedin', 'naukri', 'monster']
            if domain.lower() not in job_boards:
                company = domain.replace('-', ' ').replace('_', ' ')
                company = ' '.join(word.capitalize() for word in company.split())
                return company
                
    except Exception as e:
        print(f"⚠ Error extracting company from URL: {e}")
    
    return None

def extract_responsibilities(html):
    """Extract key responsibilities section from HTML content."""
    soup = BeautifulSoup(html, "html.parser")
    responsibilities = []
    
    # Find headings that contain "responsibility" or "responsibilities"
    headings = soup.find_all(['h2', 'h3', 'h4'])
    
    for heading in headings:
        heading_text = heading.get_text(separator=" ", strip=True).lower()
        
        if 'responsibilit' in heading_text or 'key role' in heading_text or 'duties' in heading_text:
            # Found a responsibilities section, extract content after this heading
            current = heading.find_next_sibling()
            
            while current and current.name not in ['h2', 'h3', 'h4']:
                if current.name == 'ul':
                    # Extract list items
                    for li in current.find_all('li'):
                        text = li.get_text(separator=" ", strip=True)
                        if text and len(text) > 5:  # Skip very short items
                            responsibilities.append(text)
                elif current.name == 'p':
                    # Extract paragraph text
                    text = current.get_text(separator=" ", strip=True)
                    if text and len(text) > 10:
                        responsibilities.append(text)
                
                current = current.find_next_sibling()
                
                # Limit to prevent extracting too much
                if len(responsibilities) >= 15:
                    break
            
            # If we found responsibilities, stop looking
            if responsibilities:
                break
    
    # Join responsibilities with proper formatting
    if responsibilities:
        # Ensure proper spacing and punctuation
        cleaned = [re.sub(r"\s+", " ", r).strip() for r in responsibilities[:10]]
        return "; ".join(cleaned)
    
    return ""

def extract_from_table(html):
    """Extract structured job details from HTML table if present."""
    soup = BeautifulSoup(html, "html.parser")
    extracted_data = {}
    
    # Find all tables - prioritize job details tables
    tables = soup.find_all("table")
    
    for table in tables:
        rows = table.find_all("tr")
        
        for row in rows:
            cells = row.find_all("td")
            if len(cells) == 2:
                # Get left and right cell content
                category = cells[0].get_text(strip=True).lower()
                value = cells[1].get_text(strip=True)
                
                # Skip empty values
                if not value or value == "-":
                    continue
                
                # Comprehensive field mapping
                # Company Name
                if any(x in category for x in ["company name", "company", "organization"]):
                    extracted_data["company"] = value
                
                # Job Title/Role
                elif any(x in category for x in ["job title", "role", "position", "designation"]):
                    if "title" not in extracted_data:
                        extracted_data["title"] = value
                
                # Location
                elif "location" in category:
                    extracted_data["location"] = value
                
                # Experience
                elif any(x in category for x in ["experience", "experience required", "years of experience"]):
                    extracted_data["experience"] = value
                
                # Work Mode/Type
                elif any(x in category for x in ["work mode", "work type", "internship type", "employment type"]):
                    extracted_data["jobType"] = value
                
                # Salary/CTC/Stipend
                elif any(x in category for x in ["salary", "ctc", "package", "stipend", "compensation"]):
                    extracted_data["salary"] = value
                
                # Qualification/Education/Eligibility
                elif any(x in category for x in ["qualification", "eligibility", "education", "degree"]):
                    if "requirements" not in extracted_data:
                        extracted_data["requirements"] = value
                    else:
                        extracted_data["requirements"] += "; " + value
                
                # Skills (Technology Stack, Core Skills, etc.)
                elif any(x in category for x in ["technology stack", "core skills", "skills required", "technical skills", "key skills", "required skills"]):
                    if "preferredSkills" not in extracted_data:
                        extracted_data["preferredSkills"] = value
                    else:
                        extracted_data["preferredSkills"] += "; " + value
                
                # Department
                elif "department" in category:
                    if "description" not in extracted_data:
                        extracted_data["description"] = f"Department: {value}"
                    else:
                        extracted_data["description"] += f" | Department: {value}"
                
                # Reporting To
                elif "reporting to" in category or "reports to" in category:
                    if "description" not in extracted_data:
                        extracted_data["description"] = f"Reporting To: {value}"
                    else:
                        extracted_data["description"] += f" | Reporting To: {value}"
                
                # Shift Timings
                elif "shift" in category or "timings" in category:
                    if "description" not in extracted_data:
                        extracted_data["description"] = f"Shift: {value}"
                    else:
                        extracted_data["description"] += f" | Shift: {value}"
                
                # Domain
                elif "domain" in category:
                    if "description" not in extracted_data:
                        extracted_data["description"] = f"Domain: {value}"
                    else:
                        extracted_data["description"] += f" | Domain: {value}"
                
                # Responsibility Area/Description (from Roles and Responsibilities table)
                elif "responsibility area" in category or "description" in category:
                    if "responsibilities" not in extracted_data:
                        extracted_data["responsibilities"] = value
                    else:
                        extracted_data["responsibilities"] += "; " + value
    
    return extracted_data

def extract_job_details_with_ai(title, content_html, default_link):
    soup = BeautifulSoup(content_html, "html.parser")
    clean_text = soup.get_text(separator="\n").strip()
    clean_text_for_ai = clean_text[:10000]  # Increased to 10000 chars for comprehensive content analysis and quality extraction
    
    # First, extract from table
    table_data = extract_from_table(content_html)
    
    if table_data:
        print(f"\n📋 Extracted from HTML table ({len(table_data)} fields):")
        for key, value in table_data.items():
            print(f"   ✓ {key}: {value[:80] if len(str(value)) > 80 else value}")
    
    # Extract responsibilities from HTML structure
    responsibilities = extract_responsibilities(content_html)
    if responsibilities:
        print(f"\n✓ Extracted responsibilities: {len(responsibilities)} characters")
    # --- Always try apply-link page first and merge its structured data ---
    apply_url = default_link or extract_apply_link(content_html)
    apply_table_data = {}
    apply_responsibilities = ""
    apply_html = None
    if apply_url:
        apply_html = fetch_url_html(apply_url)
        if apply_html:
            try:
                apply_table_data = extract_from_table(apply_html)
                apply_responsibilities = extract_responsibilities(apply_html)
                if apply_table_data:
                    print(f"✓ Extracted {len(apply_table_data)} fields from apply page")
            except Exception as e:
                print(f"⚠ Error extracting from apply page: {e}")

    # Merge apply page data into table_data (apply page preferred when present)
    if apply_table_data:
        for k, v in apply_table_data.items():
            if v and (k not in table_data or not table_data.get(k)):
                table_data[k] = v
                print(f"✓ Using apply-page data for {k}: {str(v)[:80]}")
    # prefer apply responsibilities if table lacked them
    if apply_responsibilities and not responsibilities:
        responsibilities = apply_responsibilities

    # Check if we have all required fields from merged table data
    required_fields = ["company", "location", "experience", "jobType"]
    has_all_required = all(field in table_data for field in required_fields)

    # Decide if we still need AI enrichment: if description or responsibilities or skills are missing or too short
    desc_len = len(table_data.get('description', '') or '')
    resp_len = len(responsibilities or '')
    has_skills = 'preferredSkills' in table_data and table_data.get('preferredSkills') and table_data.get('preferredSkills').strip() != ''

    need_ai = (not has_all_required) or (desc_len < 100) or (resp_len < 50) or (not has_skills)

    if not need_ai:
        print(f"\n✅ Table (merged) contains required fields and is sufficiently detailed - using table data directly")
        # Build job details from table data
        experience_normalized = normalize_experience(table_data.get("experience", "Not Specified"))

        job_details = {
            "company": table_data.get("company", "Not Specified"),
            "location": table_data.get("location", "Not Specified"),
            "experience": experience_normalized,
            "jobType": table_data.get("jobType", "Not Specified"),
            "salary": table_data.get("salary", "Not Disclosed"),
            "description": table_data.get("description", clean_text[:500] if clean_text else "No description available"),
            "requirements": table_data.get("requirements", "Not Specified"),
            "preferredSkills": table_data.get("preferredSkills", "Not Specified"),
            "responsibilities": table_data.get("responsibilities", responsibilities if responsibilities else "Not Specified"),
            "notificationTitle": f"New Job at {table_data.get('company', 'Company')}",
            "applyLink": apply_url or extract_apply_link(content_html) or default_link
        }

        # Log the table-extracted data
        print("\n" + "="*70)
        print("📋 TABLE-EXTRACTED JOB DATA (JSON):")
        print("="*70)
        print(json.dumps(job_details, indent=2, ensure_ascii=False))
        print("="*70 + "\n")

        return job_details

    # If after apply page merge we still need more detail, use AI to supplement
    print(f"\n🤖 Proceeding to AI enrichment if needed...")

    # If not all fields in table, use AI to supplement
    print(f"\n🤖 Using AI to supplement missing fields...")

    prompt = f"""
You are a professional job content analyzer. Read the ENTIRE job posting carefully and extract accurate, well-formatted information.

OUTPUT FORMAT: Return ONLY valid JSON with these exact fields: company, location, experience, jobType, salary, description, requirements, preferredSkills, responsibilities, skill, notificationTitle

CRITICAL INSTRUCTIONS:

1. COMPANY NAME:
   - Extract the exact company/organization name
   - Use proper capitalization (e.g., "Google", "Microsoft", "TCS")
   - If not mentioned, use "Not Specified"

2. LOCATION:
   - Include city/cities clearly (e.g., "Mumbai", "Bengaluru, Hyderabad")
   - If multiple locations, separate with commas
   - Include work mode if specified (e.g., "Mumbai (Remote)", "Pune (Hybrid)")

3. EXPERIENCE:
   - Extract experience requirement clearly
   - Format consistently: "0-2 years", "2-5 years", "5-10 years", "10+ years"
   - For freshers: use "0-2 years"
   - For experienced: extract exact range mentioned

4. JOB TYPE:
   - Use standardized terms: "Full-Time", "Part-Time", "Internship", "Contract", "Freelance"
   - Default to "Full-Time" if not clearly specified

5. SALARY:
   - Extract exact salary/CTC/stipend if mentioned (e.g., "₹5 LPA", "₹50,000/month", "₹15,000 - ₹20,000")
   - If NOT mentioned anywhere, use exactly: "Not Disclosed"
   - Include currency symbol if original has it

6. DESCRIPTION:
   - Write a comprehensive, well-structured description (250-400 words)
   - Include: role overview, what the candidate will do, key aspects of the position
   - Use proper grammar, sentence structure, and professional tone
   - Break into clear paragraphs if needed
   - Fix any grammar/spelling errors from source
   - Make it engaging and informative

7. REQUIREMENTS:
   - List ALL educational and eligibility requirements clearly
   - Format: "Bachelor's degree in Computer Science; Strong communication skills; Team player"
   - Separate multiple requirements with semicolons
   - Include mandatory qualifications, certifications, or prerequisites
   - Fix grammar and make concise

8. PREFERRED SKILLS:
   - Extract ALL technical and professional skills mentioned
   - Format clearly: "JavaScript, React, Node.js, Python, SQL, Git, Agile methodology"
   - Separate skills with commas
   - Prioritize technical skills first, then soft skills
   - Use standard skill names (e.g., "React.js" not "react")

10. RESPONSIBILITIES:
    - Provide a clear list of key responsibilities as short bullets (3-10 items)
    - Each item should be concise (6-25 words)
    - Return responsibilities as either a JSON array or a string; parser will normalize to semicolon-separated string
    - Prioritize action-oriented verbs ("Design", "Develop", "Maintain")

11. SKILL:
    - Provide a canonical, comma-separated skill list (same as `preferredSkills`) in the field `skill`

9. NOTIFICATION TITLE:
   - Create an engaging, concise title (max 60 characters)
   - Format: "New Job at [Company Name]" or "Hiring [Role] at [Company]"
   - Use proper capitalization

QUALITY STANDARDS:
✓ Correct all grammar and spelling errors
✓ Use professional, clear language
✓ Ensure proper punctuation and capitalization
✓ Remove duplicates and redundant information
✓ Maintain consistency across all fields
✓ Cross-verify information accuracy

Job Title: {title}

Job Content:
{clean_text_for_ai}

Return ONLY the JSON object, no explanations or markdown."""

    # If SKIP_AI is enabled, build a structured fallback from available content
    if SKIP_AI:
        print("⚠ SKIP_AI enabled — not calling OpenAI. Building fallback description and responsibilities from page content.")
        # Prefer table/apply data if present
        desc_parts = []
        if table_data.get('description'):
            desc_parts.append(table_data.get('description'))
        if responsibilities:
            desc_parts.append("Responsibilities: " + responsibilities)
        if table_data.get('requirements'):
            desc_parts.append("Requirements: " + table_data.get('requirements'))
        # include a short excerpt from the page content if still small
        if not desc_parts:
            desc_text = clean_text[:200]
            desc_parts.append(desc_text)

        description = "\n\n".join(desc_parts)
        # ensure reasonable length
        if len(description.split()) < 120:
            description = (description + "\n\n" + clean_text[:400]).strip()

        job_details = {
            "company": table_data.get('company', 'Not Specified'),
            "location": table_data.get('location', 'Not Specified'),
            "experience": table_data.get('experience', 'Not Specified'),
            "jobType": table_data.get('jobType', 'Not Specified'),
            "salary": table_data.get('salary', 'Not Disclosed'),
            "description": description,
            "requirements": table_data.get('requirements', 'Not Specified'),
            "preferredSkills": table_data.get('preferredSkills', 'Not Specified'),
            "responsibilities": responsibilities if responsibilities else table_data.get('responsibilities', 'Not Specified'),
            "notificationTitle": f"New Job at {table_data.get('company','Company')}"
        }

    else:
        # Call OpenAI to extract structured fields and fall back to table data on error
        try:
            response = _openai_client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
            )
            response_text = response.choices[0].message.content.strip()
            if response_text.startswith("```"):
                response_text = re.sub(r'^```json?\n', '', response_text)
                response_text = re.sub(r'\n```$', '', response_text)

            job_details = json.loads(response_text)

            # Create a better description fallback from content
            fallback_description = clean_text[:500] if clean_text else "No description available"

            defaults = {
                "company": "Not Specified",
                "location": "Not Specified",
                "experience": "Not Specified",
                "jobType": "Not Specified",
                "salary": "Not Disclosed",
                "description": fallback_description,
                "requirements": "Not Specified",
                "preferredSkills": "Not Specified",
                "responsibilities": responsibilities if responsibilities else "Not Specified",
                "notificationTitle": f"New Job at {job_details.get('company','Company')}"
            }

            for key, value in defaults.items():
                if key not in job_details or not job_details[key] or str(job_details[key]).strip() == "":
                    job_details[key] = value

            # Add extracted responsibilities if not in table (medium priority)
            if responsibilities and "responsibilities" not in table_data:
                job_details["responsibilities"] = responsibilities

            # Override with table data (highest priority)
            for key, value in table_data.items():
                if value and str(value).strip():
                    job_details[key] = value
                    print(f"✓ Using table data for {key}: {value[:80] if len(str(value)) > 80 else value}")

            # Add apply link before logging
            job_details["applyLink"] = extract_apply_link(content_html) or default_link

            # Normalize experience to standard year ranges
            experience = job_details.get("experience", "Not Specified")
            normalized_exp = normalize_experience(experience)
            if normalized_exp != experience:
                job_details["experience"] = normalized_exp
                print(f"✓ Normalized experience: '{experience}' → '{normalized_exp}'")

            # Normalize responsibilities: accept lists or strings and produce semicolon-separated string
            resp = job_details.get("responsibilities", "")
            if isinstance(resp, list):
                resp_list = [re.sub(r"\s+", " ", r).strip() for r in resp if r and len(str(r).strip()) > 3]
                job_details["responsibilities"] = "; ".join(resp_list)
            elif isinstance(resp, str):
                parts = re.split(r"\n|\r|•|‣|◦|;|\-|\u2022|\u2023|\u25E6", resp)
                parts = [p.strip(" \t-•‣◦") for p in parts]
                parts = [p for p in parts if p and len(p) > 3]
                if parts:
                    job_details["responsibilities"] = "; ".join(parts)
                else:
                    job_details["responsibilities"] = resp.strip()

            # Normalize preferredSkills to comma-separated string
            prefs = job_details.get("preferredSkills", "")
            if isinstance(prefs, list):
                prefs_list = [re.sub(r"\s+", " ", s).strip() for s in prefs if s and len(str(s).strip()) > 1]
                job_details["preferredSkills"] = ", ".join(prefs_list)
            elif isinstance(prefs, str):
                s = prefs.replace(";", ",")
                s = re.sub(r",\s*", ", ", s)
                job_details["preferredSkills"] = s.strip()

            # Ensure singular 'skill' field exists (same as preferredSkills)
            job_details["skill"] = job_details.get("preferredSkills", "Not Specified")

            # Log description extraction and length
            description = job_details.get("description", "")
            if description:
                desc_length = len(description)
                word_count = len(description.split())
                print(f"✓ Extracted description: {desc_length} characters, {word_count} words")

            # If description is too short and AI is available, ask AI to expand to 250-350 words
            if not SKIP_AI and OPENAI_API_KEY:
                try:
                    word_count = len(description.split())
                    if word_count < 200:
                        expand_prompt = f"Expand the following job description to be between 250 and 350 words, professional tone, keep facts unchanged.\n\nCurrent description:\n{description}\n\nAlso ensure responsibilities are preserved: {job_details.get('responsibilities','')}. Return only the expanded description text."
                        exp_resp = _openai_client.chat.completions.create(
                            model=OPENAI_MODEL,
                            messages=[{"role": "user", "content": expand_prompt}],
                            temperature=0.2,
                        )
                        expanded_text = exp_resp.choices[0].message.content.strip()
                        if expanded_text:
                            job_details["description"] = expanded_text
                            print(f"✓ Expanded description to {len(expanded_text.split())} words via AI")
                except Exception as ee:
                    print(f"⚠ Description expansion failed: {ee}")

            # Update notification title with correct company name
            company_name = job_details.get("company", "Company")
            if company_name != "Not Specified":
                job_details["notificationTitle"] = f"New Job at {company_name}"

            # Log the AI-curated JSON data
            print("\n" + "="*70)
            print("🤖 AI-CURATED JOB DATA (JSON):")
            print("="*70)
            print(json.dumps(job_details, indent=2, ensure_ascii=False))
            print("="*70 + "\n")

            return job_details

        except Exception as e:
            print(f"⚠ AI extraction failed: {e}")

            # Use table data as fallback
            experience_raw = table_data.get("experience", "Not Specified")
            experience_normalized = normalize_experience(experience_raw)

            # Use table description if available, otherwise extract from content
            description = table_data.get("description", clean_text[:500] if clean_text else "No description available")

            fallback_data = {
                "company": table_data.get("company", "Not Specified"),
                "location": table_data.get("location", "Not Specified"),
                "experience": experience_normalized,
                "jobType": table_data.get("jobType", "Not Specified"),
                "salary": table_data.get("salary", "Not Disclosed"),
                "description": description,
                "requirements": table_data.get("requirements", "Not Specified"),
                "preferredSkills": table_data.get("preferredSkills", "Not Specified"),
                "responsibilities": responsibilities if responsibilities else "Not Specified",
                "notificationTitle": f"New Job at {table_data.get('company', 'Company')}",
                "applyLink": extract_apply_link(content_html) or default_link
            }

            print(f"✓ Using table-extracted data as fallback")
            return fallback_data

def save_job(job):
    title_html = job.get("title", {}).get("rendered", "")
    content_html = job.get("content", {}).get("rendered", "")
    link = job.get("link", "")

    clean_title = BeautifulSoup(title_html, "html.parser").get_text()

    # Check for duplicates by applyLink (primary check)
    existing_by_link = list(db.collection("Directjobs").where("applyLink", "==", link).limit(1).stream())
    if existing_by_link:
        print(f"⏭️  Skipped: {clean_title[:60]}... (Already exists - same apply link)")
        return "DUPLICATE"
    
    # Check for duplicates by title (secondary check for same job with different link)
    existing_by_title = list(db.collection("Directjobs").where("title", "==", clean_title).limit(1).stream())
    if existing_by_title:
        print(f"⏭️  Skipped: {clean_title[:60]}... (Already exists - same title)")
        return "DUPLICATE"

    ai_data = extract_job_details_with_ai(clean_title, content_html, link)
    
    # Validate company name - try to extract from URL if not found
    company_name = ai_data.get("company", "").strip()
    invalid_companies = ["not specified", "unknown", "company", "", "n/a", "na", "not available"]
    
    if not company_name or company_name.lower() in invalid_companies:
        # Try to extract company name from apply link as fallback
        apply_link = ai_data.get("applyLink", link)
        company_from_url = extract_company_from_url(apply_link)
        
        if company_from_url:
            ai_data["company"] = company_from_url
            company_name = company_from_url
            print(f"✓ Extracted company from URL: {company_name}")
        else:
            print(f"❌ Skipped: {clean_title[:60]}... (Company name not found)")
            return None
    
    # Add jobFor classification
    job_for = classify_job(clean_title, content_html)
    ai_data["jobFor"] = job_for
    
    # Update notification title with correct company name
    if company_name and company_name != "Not Specified":
        ai_data["notificationTitle"] = f"New Job at {company_name}"
    
    now = datetime.now(IST)
    
    # Generate unique job ID
    global job_counter
    unique_jobid = f"scrap{job_counter:02d}"
    job_counter += 1

    job_data = {
        "active": True,
        "approved": True,
        "title": clean_title,
        "company": ai_data.get("company"),
        "location": ai_data.get("location"),
        "experience": ai_data.get("experience"),
        "jobType": ai_data.get("jobType"),
        "salary": ai_data.get("salary") or "Not Disclosed",
        "description": ai_data.get("description"),
        "requirements": ai_data.get("requirements"),
        "preferredSkills": ai_data.get("preferredSkills"),
        "skill": ai_data.get("preferredSkills"),
        "responsibilities": ai_data.get("responsibilities", "Not Specified"),
        "applyLink": ai_data.get("applyLink"),
        "jobid": unique_jobid,
        "jobposterid": "",
        "source": "jobcode.in",
        "sourceFile": "scrape_jobcode_to_firestore.py",
        "jobFor": job_for,
        "createdAt": now,
        "postedAt": now,
    }
    
    # Log complete job data being saved to Firebase
    print("\n" + "="*70)
    print("📝 POSTING JOB TO FIREBASE:")
    print("="*70)
    print(json.dumps({k: str(v) if k in ["createdAt", "postedAt"] else v for k, v in job_data.items()}, indent=2, ensure_ascii=False))
    print("="*70 + "\n")

    # Post to Firebase
    db.collection("Directjobs").add(job_data)
    print(f"✓ Added to Firebase: {clean_title} (ID: {unique_jobid})")
    return ai_data.get("notificationTitle")

def get_highest_scrap_id():
    """Get the highest scrap ID from existing jobs in Firebase"""
    try:
        jobs = db.collection("Directjobs").where("jobid", ">=", "scrap").where("jobid", "<", "scraq").stream()
        max_id = 0
        for job in jobs:
            job_data = job.to_dict()
            jobid = job_data.get("jobid", "")
            if jobid.startswith("scrap"):
                try:
                    num = int(jobid.replace("scrap", ""))
                    if num > max_id:
                        max_id = num
                except ValueError:
                    continue
        return max_id
    except Exception as e:
        print(f"⚠ Error getting highest scrap ID: {e}")
        return 0

def send_notification(title):
    tokens = []
    users = db.collection("users").stream()
    for user in users:
        token_docs = db.collection("users").document(user.id).collection("deviceTokens").stream()
        for token_doc in token_docs:
            token = token_doc.to_dict().get("token")
            if token:
                tokens.append(token)

    if not tokens:
        print("No device tokens found.")
        return

    message = messaging.MulticastMessage(
        notification=messaging.Notification(
            title="🚀 New Job Alert!",
            body=title,
        ),
        android=messaging.AndroidConfig(
            priority='high',
            notification=messaging.AndroidNotification(
                sound='default',
                channel_id='job_alerts',
                priority='high',
            )
        ),
        apns=messaging.APNSConfig(
            payload=messaging.APNSPayload(
                aps=messaging.Aps(
                    sound='default',
                    badge=1,
                    content_available=True,
                )
            )
        ),
        tokens=tokens
    )

    response = messaging.send_each_for_multicast(message)
    print("✓ Notification sent")
    print("  Success:", response.success_count)
    print("  Failed:", response.failure_count)

# ------------------ MAIN ------------------
if __name__ == "__main__":
    # Get the highest existing scrap ID
    print("🔍 Checking existing scrap IDs in Firebase...")
    highest_id = get_highest_scrap_id()
    job_counter = highest_id + 1
    print(f"✓ Starting from scrap{job_counter:02d}\n")
    
    page = 1
    latest_notification_title = None
    jobs_processed = 0
    jobs_skipped = 0
    jobs_duplicates = 0
    jobs_added = 0
    jobs_no_company = 0

    today = datetime.now(IST).date()
    
    print("\n" + "="*70)
    print("🚀 SCRAPING LATEST JOBS FROM JOBCODE.IN")
    print(f"   Date: {today}")
    print("   ✅ New jobs will be posted to Firebase")
    print("   📢 Notifications will be sent")
    print("="*70 + "\n")

    while True:
        jobs = fetch_jobs_page(page)
        if jobs is None:
            print("❌ Persistent network failure detected. Exiting scraper.")
            sys.exit(1)
        if not jobs:
            break

        for job in jobs:
            # Process latest jobs (today and yesterday to catch any missed)
            job_date_str = job.get("date")
            if job_date_str:
                job_date = datetime.fromisoformat(job_date_str.replace("Z", "+00:00")).astimezone(IST).date()
                
                # Only process today's jobs (skip older ones)
                days_old = (today - job_date).days
                if days_old > 1:  # Skip jobs older than yesterday
                    continue

            notification_title = save_job(job)
            if notification_title == "DUPLICATE":
                jobs_duplicates += 1
            elif notification_title:
                latest_notification_title = notification_title
                jobs_added += 1
            else:
                jobs_no_company += 1
            
            jobs_processed += 1
            time.sleep(0.5)  # prevent overload

        page += 1

    # Send notification for the latest added job
    if latest_notification_title:
        try:
            send_notification(latest_notification_title)
            print("\n✅ Notification sent for the latest job.")
        except Exception as e:
            print(f"\n⚠ Notification failed: {e}")
    else:
        print("\n⏭️  No new jobs added. No notifications sent.")
    
    print("\n" + "="*70)
    if jobs_added == 0:
        print("❌ NO NEW JOBS FOUND")
        print("="*70)
        print(f"   Jobs Checked: {jobs_processed}")
        print(f"   Jobs Skipped (Duplicates): {jobs_duplicates}")
        print(f"   Jobs Skipped (No Company Name): {jobs_no_company}")
        print(f"   Jobs Added to Firebase: {jobs_added}")
        print("="*70)
        print("ℹ️  All jobs are already in the database or were filtered out")
        print("="*70 + "\n")
    else:
        print("📊 PROCESSING SUMMARY")
        print("="*70)
        print(f"   Jobs Skipped (Duplicates): {jobs_duplicates}")
        print(f"   Jobs Skipped (No Company Name): {jobs_no_company}")
        print(f"   Jobs Added to Firebase: {jobs_added}")
        print(f"   Total Jobs Processed: {jobs_processed}")
        print("="*70)
        print("✅ Jobs successfully posted to Firebase")
        print("="*70 + "\n")
