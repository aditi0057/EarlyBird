"""
filters.py  --  the rules that decide which jobs are relevant to you.

Shared by the monitor (fetch_jobs.py) and the discovery tool (discover_boards.py)
so both judge "is this a role for me?" the same way.

Everything here is YOURS to tune.
"""

import re

# A job's TITLE must contain at least one of these words (case-insensitive).
ROLE_KEYWORDS = [
    "software engineer",
    "backend",
    "frontend",
    "full stack",
    "full-stack",
    "developer",
    "sde",
    "engineer",
    "software development",
    "data engineer",
    "platform engineer",
]

# A job's LOCATION must contain at least one of these words.
LOCATION_KEYWORDS = [
    "india",
    "bengaluru",
    "bangalore",
    "hyderabad",
    "pune",
    "gurgaon",
    "gurugram",
    "noida",
    "delhi",
    "mumbai",
    "chennai",
]

# If a job TITLE contains any of these, we DROP it.
#   (A) SENIORITY — above your level for now. Remove as you gain experience.
#   (B) NON-SWE ROLE TYPES — titles that contain "engineer" but aren't core
#       software-development jobs.
EXCLUDE_TITLE_KEYWORDS = [
    # (A) Seniority
    "senior",
    "sr.",
    "manager",
    "director",
    "staff",
    "principal",
    "senior staff",
    "head of",
    "vp",
    "vice president",
    "lead",
    "architect",
    # (B) Non-SWE role types that sometimes contain "engineer"
    "support",
    "sales",
    "solutions",
    "customer success",
    "account executive",
    "field",
    "presales",
    "pre-sales",
    "recruiter",
    "designer",
    "product manager",
    "program manager",
    "marketing",
]


# Some titles hide seniority as an experience range, e.g. "(7 to 11 years)"
# or "5+ years". If the title demands this many years or more, drop it.
MIN_SENIOR_YEARS = 4
_YEARS_RE = re.compile(
    r"(\d+)\s*\+?\s*(?:to|-|–|—)?\s*\d*\s*(?:years|year|yrs|yr)\b", re.IGNORECASE
)


def has_whole_word(text, word):
    """True if `word` appears as a whole word in `text` (case-insensitive)."""
    return re.search(r"\b" + re.escape(word) + r"\b", text) is not None


def seems_senior_by_years(title):
    """True if the title states an experience requirement of MIN_SENIOR_YEARS+."""
    return any(int(n) >= MIN_SENIOR_YEARS for n in _YEARS_RE.findall(title))


def matches(job):
    """Return True if a job's title and location pass our filters."""
    title = (job.get("title") or "").lower()
    location = (job.get("location", {}).get("name") or "").lower()

    title_ok = any(has_whole_word(title, w) for w in ROLE_KEYWORDS)
    location_ok = any(has_whole_word(location, w) for w in LOCATION_KEYWORDS)
    excluded = any(has_whole_word(title, w) for w in EXCLUDE_TITLE_KEYWORDS)
    return title_ok and location_ok and not excluded and not seems_senior_by_years(title)
