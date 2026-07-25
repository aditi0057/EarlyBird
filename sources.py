"""
sources.py  --  fetch jobs from multiple job-board providers (ATS).

Each company in companies.json has a "source" (greenhouse / lever / ashby) and a
"token" (its id on that provider). This module knows how to talk to each provider
and returns jobs in ONE common shape so the rest of the system doesn't care where
a job came from:

    {
      "id": <str/int>,
      "title": <str>,
      "location": {"name": <str>},
      "absolute_url": <str>,     # link to apply
      "_source": <str>,          # which provider
      "_token": <str>,           # the company's token on that provider
      "_content": <str or None>, # full job description text, if the API gave it
    }

Adding a new provider later = write one fetch function + register it in FETCHERS.
"""

import re
import html

import requests
import truststore
truststore.inject_into_ssl()


def strip_html(raw):
    """Turn HTML job content into readable plain text."""
    text = html.unescape(raw or "")
    text = re.sub(r"<\s*br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"</\s*(p|li|div|h\d)\s*>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# ----------------------------------------------------------------------------
# Per-provider fetchers. Each takes a token and returns a list of RAW jobs from
# that API; normalisation to the common shape happens in the wrappers below.
# ----------------------------------------------------------------------------

# A browser-like User-Agent — some big-company sites reject generic clients.
_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) job-monitor/1.0"
_HEADERS = {"User-Agent": _UA, "Accept": "application/json"}


def _get_json(url):
    r = requests.get(url, timeout=25, headers=_HEADERS)
    r.raise_for_status()
    return r.json()


def _post_json(url, payload):
    r = requests.post(url, json=payload, timeout=25, headers=_HEADERS)
    r.raise_for_status()
    return r.json()


def fetch_greenhouse(token):
    data = _get_json(f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs")
    out = []
    for j in data.get("jobs", []):
        out.append({
            "id": j.get("id"),
            "title": j.get("title") or "",
            "location": {"name": (j.get("location") or {}).get("name", "")},
            "absolute_url": j.get("absolute_url", ""),
            "_source": "greenhouse",
            "_token": token,
            "_content": None,  # greenhouse needs a per-job call for the description
        })
    return out


def fetch_lever(token):
    data = _get_json(f"https://api.lever.co/v0/postings/{token}?mode=json")
    out = []
    for j in data:
        cats = j.get("categories") or {}
        out.append({
            "id": j.get("id"),
            "title": j.get("text") or "",
            "location": {"name": cats.get("location", "") or ""},
            "absolute_url": j.get("hostedUrl", ""),
            "_source": "lever",
            "_token": token,
            "_content": j.get("descriptionPlain") or strip_html(j.get("description", "")),
        })
    return out


def fetch_ashby(token):
    data = _get_json(f"https://api.ashbyhq.com/posting-api/job-board/{token}?includeCompensation=false")
    out = []
    for j in data.get("jobs", []):
        out.append({
            "id": j.get("id"),
            "title": j.get("title") or "",
            "location": {"name": j.get("location") or ""},
            "absolute_url": j.get("jobUrl") or j.get("applyUrl") or "",
            "_source": "ashby",
            "_token": token,
            "_content": j.get("descriptionPlain") or strip_html(j.get("descriptionHtml", "")),
        })
    return out


def fetch_amazon(token="india"):
    """Amazon jobs. token is unused (single company); we query India software roles.
    Amazon's loc_query is a soft filter, so we also rely on the location filter later."""
    base = "https://www.amazon.jobs"
    out = []
    for offset in (0, 100):  # two pages of 100
        url = (f"{base}/en/search.json?loc_query=India&country=IND"
               f"&base_query=software%20development%20engineer"
               f"&result_limit=100&offset={offset}&sort=recent")
        try:
            data = _get_json(url)
        except (requests.RequestException, ValueError):
            break
        jobs = data.get("jobs", [])
        if not jobs:
            break
        for j in jobs:
            out.append({
                "id": j.get("id_icims") or j.get("id"),
                "title": j.get("title") or "",
                "location": {"name": j.get("normalized_location") or j.get("city") or ""},
                "absolute_url": base + (j.get("job_path") or ""),
                "_source": "amazon",
                "_token": "india",
                "_content": strip_html(j.get("description_short") or j.get("description") or ""),
            })
    return out


def fetch_workday(token):
    """Workday board. token = 'tenant:datacenter:site', e.g. 'ms:wd5:External'.
    Returns up to ~100 software roles; the location filter narrows to India later."""
    tenant, dc, site = token.split(":")
    base = f"https://{tenant}.{dc}.myworkdayjobs.com"
    api = f"{base}/wday/cxs/{tenant}/{site}/jobs"
    out = []
    offset = 0
    for _ in range(5):  # up to 5 pages x 20 = 100
        data = _post_json(api, {"limit": 20, "offset": offset,
                                "searchText": "software engineer", "appliedFacets": {}})
        jps = data.get("jobPostings") or []
        if not jps:
            break
        for j in jps:
            ep = j.get("externalPath") or ""
            out.append({
                "id": ep,
                "title": j.get("title") or "",
                "location": {"name": j.get("locationsText") or ""},
                "absolute_url": f"{base}/{site}{ep}",
                "_source": "workday",
                "_token": token,
                "_content": None,  # fetched on demand via fetch_workday_description
            })
        offset += 20
        if offset >= data.get("total", 0):
            break
    return out


def fetch_workday_description(token, external_path):
    """Fetch the full job description text for one Workday job (used for tailoring)."""
    tenant, dc, site = token.split(":")
    base = f"https://{tenant}.{dc}.myworkdayjobs.com"
    data = _get_json(f"{base}/wday/cxs/{tenant}/{site}{external_path}")
    return strip_html((data.get("jobPostingInfo") or {}).get("jobDescription", ""))


FETCHERS = {
    "greenhouse": fetch_greenhouse,
    "lever": fetch_lever,
    "ashby": fetch_ashby,
    "amazon": fetch_amazon,
    "workday": fetch_workday,
}


def fetch_jobs_for(company, quiet=False):
    """Fetch + normalise jobs for one company dict {name, source, token}.
    Returns [] on any error so one bad board never stops the run."""
    source = company.get("source", "greenhouse")
    fn = FETCHERS.get(source)
    if not fn:
        if not quiet:
            print(f"  [!] Unknown source '{source}' for {company.get('name')}")
        return []
    try:
        return fn(company["token"])
    except (requests.RequestException, ValueError) as e:
        if not quiet:
            print(f"  [!] Could not reach {company.get('name')} ({source}): {e}")
        return []


def probe(source, token):
    """For discovery: is this a real board? Returns (is_real, jobs_list)."""
    fn = FETCHERS.get(source)
    if not fn:
        return (False, [])
    try:
        jobs = fn(token)
        return (True, jobs)
    except (requests.RequestException, ValueError):
        return (False, [])
