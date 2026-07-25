"""
fetch_jobs.py  --  the monitor: discover -> filter -> tailor -> alert.

WHAT THIS DOES (in plain words):
  Every run it asks each company (in companies.json) for its live jobs across
  Greenhouse / Lever / Ashby, keeps the ones that look like an engineering role
  in India, and for anything NEW it: builds a tailored resume + referral kit,
  saves it under kits/, and pushes a summary to your phone.

  Runs by hand (py fetch_jobs.py) or automatically via the Windows scheduled
  task "JobMonitor" (every 2 hours).

WHAT TO EDIT:
  - companies.json  -> which companies to watch (grow it with discover_boards.py)
  - filters.py      -> which roles/locations count as relevant to you
  - config.local.json -> your keys, name, school, toggles
Everything below is the engine.
"""

import os
import sys
import json
import hashlib
import datetime
from concurrent.futures import ThreadPoolExecutor

from notify import is_configured, send_push_actions, approve_topic, load_config

# ----------------------------------------------------------------------------
# Logging: mirror everything we print into monitor.log (background runs have no
# console; sys.stdout can even be None). Tee all output so runs leave history.
# ----------------------------------------------------------------------------
_LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "monitor.log")
_log_file = open(_LOG_PATH, "a", encoding="utf-8", buffering=1)


class _Tee:
    """Write to several streams at once (console + log file)."""
    def __init__(self, *streams):
        self.streams = [s for s in streams if s is not None]

    def write(self, data):
        for s in self.streams:
            try:
                s.write(data)
            except (ValueError, OSError):
                pass

    def flush(self):
        for s in self.streams:
            try:
                s.flush()
            except (ValueError, OSError):
                pass


_console = sys.stdout
if _console is not None:
    try:
        _console.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        _console = None

sys.stdout = _Tee(_console, _log_file)
sys.stderr = sys.stdout

import truststore
truststore.inject_into_ssl()

from filters import matches
from sources import fetch_jobs_for
from tailor_resume import load_resume, quick_assess
from kit import get_jd

HERE = os.path.dirname(os.path.abspath(__file__))
COMPANIES_FILE = os.path.join(HERE, "companies.json")
SEEN_FILE = os.path.join(HERE, "seen_jobs.json")
PENDING_FILE = os.path.join(HERE, "pending.json")

# How many NEW roles to alert per run. Un-alerted extras are NOT marked seen,
# so they get alerted on the next run (natural throttle, nothing lost).
MAX_ALERTS_PER_RUN = 10

# How many company boards to fetch at once (parallel network calls).
FETCH_WORKERS = 12


def load_companies():
    """Read the watch-list. Falls back to a tiny built-in list if missing."""
    if not os.path.exists(COMPANIES_FILE):
        print(f"  [!] {os.path.basename(COMPANIES_FILE)} not found — run discover_boards.py.")
        return [{"name": "Okta", "source": "greenhouse", "token": "okta", "type": "tech"}]
    try:
        with open(COMPANIES_FILE, "r", encoding="utf-8-sig") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"  [!] Could not read companies.json: {e}")
        return []


def load_seen():
    if not os.path.exists(SEEN_FILE):
        return set()
    try:
        with open(SEEN_FILE, "r", encoding="utf-8-sig") as f:
            return set(json.load(f))
    except (json.JSONDecodeError, OSError):
        return set()


def save_seen(seen_keys):
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted(seen_keys), f, indent=2)


def job_key(company_name, job):
    """A stable, unique ID for a job so we recognise it across runs."""
    return f"{company_name}:{job.get('id')}"


def print_job(company_name, job):
    title = job.get("title", "Untitled role")
    location = (job.get("location") or {}).get("name", "Unknown location")
    link = job.get("absolute_url", "")
    print(f"\n[{company_name}] {title}")
    print(f"   Location: {location}")
    print(f"   Apply:    {link}")


# ============================================================================
# PENDING + ALERTS  --  notify with a tap-to-approve button; build only on tap.
# ============================================================================

def load_pending():
    if not os.path.exists(PENDING_FILE):
        return {}
    try:
        with open(PENDING_FILE, "r", encoding="utf-8-sig") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


MAX_PENDING = 80  # cap so un-approved alerts don't accumulate forever


def save_pending(pending):
    # Keep only the most recently added entries (dicts preserve insertion order).
    if len(pending) > MAX_PENDING:
        pending = dict(list(pending.items())[-MAX_PENDING:])
    with open(PENDING_FILE, "w", encoding="utf-8") as f:
        json.dump(pending, f, indent=2)


def short_id(company_name, job):
    """A short, stable id used as the approval token in the ntfy button."""
    return hashlib.sha1(job_key(company_name, job).encode("utf-8")).hexdigest()[:10]


def alert_new_role(company_name, job, role_type, pending, cfg, resume):
    """Push a tap-to-approve notification for one new role; record it as pending.

    Includes a JD-specific strength + gaps line (a cheap assessment); the full
    tailored PDF + referral is built only when you tap Make Kit.
    """
    sid = short_id(company_name, job)
    title = job.get("title", "Untitled role")
    location = (job.get("location") or {}).get("name", "")
    apply_url = job.get("absolute_url", "")

    pending[sid] = {"company": company_name, "role_type": role_type, "job": job}

    strength, gaps = "", ""
    if resume and cfg.get("gemini_api_key"):
        try:
            jd = get_jd(job)
            a = quick_assess(resume, jd, cfg)
            strength, gaps = a.get("strength", ""), a.get("gaps", "")
        except Exception as e:
            print(f"  [!] assess failed for {company_name}: {e}")

    lines = [f"**{company_name}** — {title}", location]
    if strength:
        lines.append(f"\n💪 {strength}")
    if gaps and gaps.strip().lower().rstrip(".") not in ("none obvious", "none", ""):
        lines.append(f"⚠️ Gaps: {gaps}")
    lines.append("\nTap **Make Kit** for the tailored resume PDF + referral.")

    actions = [
        {"action": "http", "label": "✅ Make Kit",
         "url": f"https://ntfy.sh/{approve_topic()}", "method": "POST",
         "body": sid, "clear": True},
    ]
    if apply_url:
        actions.append({"action": "view", "label": "Open role", "url": apply_url})
    return send_push_actions(f"New match: {company_name}", "\n".join(lines), actions)


def fetch_all(companies):
    """Fetch every company's jobs in parallel. Returns list of (company, jobs)."""
    results = []

    def one(company):
        return company, fetch_jobs_for(company, quiet=True)

    with ThreadPoolExecutor(max_workers=FETCH_WORKERS) as pool:
        for company, jobs in pool.map(one, companies):
            results.append((company, jobs))
    return results


def main():
    print(f"\n===== Run started: {datetime.datetime.now():%Y-%m-%d %H:%M:%S} =====")
    companies = load_companies()
    type_by_name = {c["name"]: c.get("type", "tech") for c in companies}
    seen = load_seen()
    first_run = len(seen) == 0

    print(f"Checking {len(companies)} companies ...")
    all_matches = []
    for company, jobs in fetch_all(companies):
        kept = [j for j in jobs if matches(j)]
        if kept:
            print(f"  {company['name']}: {len(jobs)} jobs, {len(kept)} match.")
        for job in kept:
            all_matches.append((company["name"], job))

    new_matches = [
        (name, job) for name, job in all_matches
        if job_key(name, job) not in seen
    ]

    print("\n" + "=" * 70)
    if first_run:
        # Baseline: record everything, alert nothing.
        print(f"  FIRST RUN: recording {len(all_matches)} current roles as your baseline.")
        print("  From the NEXT run on, you'll only be alerted to NEW roles.")
        print("=" * 70)
        for name, job in all_matches:
            seen.add(job_key(name, job))
        save_seen(seen)
        return

    if not new_matches:
        print(f"  No new roles since last check. ({len(all_matches)} matching roles watched.)")
        print("=" * 70)
        return

    print(f"  {len(new_matches)} NEW ROLE(S)! Alerting up to {MAX_ALERTS_PER_RUN} this run.")
    print("=" * 70)

    cfg = load_config()
    resume = load_resume()
    pending = load_pending()
    to_alert = new_matches[:MAX_ALERTS_PER_RUN]
    alerted = 0
    for company_name, job in to_alert:
        print_job(company_name, job)
        if is_configured():
            ok = alert_new_role(company_name, job, type_by_name.get(company_name, "tech"),
                                pending, cfg, resume)
            if ok:
                seen.add(job_key(company_name, job))  # only mark seen once alerted
                alerted += 1
        else:
            seen.add(job_key(company_name, job))

    save_pending(pending)
    save_seen(seen)

    leftover = len(new_matches) - len(to_alert)
    print(f"\n  Alerted {alerted} role(s) with a tap-to-approve button.")
    if leftover > 0:
        print(f"  ({leftover} more new role(s) will be alerted next run.)")


if __name__ == "__main__":
    main()
