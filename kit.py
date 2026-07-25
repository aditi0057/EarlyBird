"""
kit.py  --  build one job's full application kit:
  - a tailored, ready-to-apply resume PDF (matches your layout)
  - a referral file (LinkedIn links + message drafts in your style)
  - a short fit/gaps summary

Used by approvals.py (when you tap "Make Kit") and can be called directly.
Never called for every job automatically — only on your approval — so no waste.
"""

import os
import re
import datetime

from tailor_resume import (
    load_config, load_resume, generate_kit_data,
    fetch_jd_by_token_id,
)
from resume_pdf import render_resume
from referrals import build_referral_md, referral_message

HERE = os.path.dirname(os.path.abspath(__file__))
KITS_DIR = os.path.join(HERE, "kits")


def _safe(text):
    return re.sub(r"[^A-Za-z0-9._-]+", "_", str(text)).strip("_")[:80]


def get_jd(job):
    """Get the job description text for a normalized job dict, whatever its source."""
    title = job.get("title", "")
    location = (job.get("location") or {}).get("name", "")
    content = job.get("_content")
    if content:
        return f"{title}\n\n{content}"
    source, token, jid = job.get("_source"), job.get("_token"), job.get("id")
    try:
        if source == "greenhouse" and token:
            return fetch_jd_by_token_id(token, jid)
        if source == "workday" and token:
            from sources import fetch_workday_description
            return f"{title}\n\n{fetch_workday_description(token, jid)}"
    except Exception:
        pass
    return f"{title}\n{location}"


def build_full_kit(company_name, job, role_type, cfg=None):
    """Build the PDF + referral kit for one job.

    Returns dict {pdf_path, md_path, fit, gaps, title, apply_url, message} or None.
    """
    cfg = cfg or load_config()
    resume = load_resume()
    if resume is None or not cfg.get("gemini_api_key"):
        print("  [!] Missing resume.md or gemini_api_key — cannot build kit.")
        return None

    title = job.get("title", "Untitled role")
    location = (job.get("location") or {}).get("name", "")
    apply_url = job.get("absolute_url", "")
    role_only = title.split(",")[0].split("(")[0].strip()

    try:
        jd = get_jd(job)
        data = generate_kit_data(resume, jd, cfg, role_type=role_type)
    except Exception as e:
        print(f"  [!] Kit failed for {company_name} - {title}: {e}")
        return None

    resume_data = data.get("resume", {})
    fit = data.get("fit", "")
    gaps = data.get("gaps", "")
    rtype = data.get("role_type", role_type or "tech")

    os.makedirs(KITS_DIR, exist_ok=True)
    base = f"{_safe(company_name)}__{_safe(role_only)}__{_safe(job.get('id'))}"
    pdf_path = os.path.join(KITS_DIR, base + ".pdf")
    md_path = os.path.join(KITS_DIR, base + ".md")

    try:
        render_resume(resume_data, pdf_path)
    except Exception as e:
        print(f"  [!] PDF render failed for {company_name} - {title}: {e}")
        pdf_path = None

    referral_md = build_referral_md(company_name, role_only, apply_url, cfg, rtype)
    message = referral_message(company_name, role_only, apply_url, cfg, rtype)

    with open(md_path, "w", encoding="utf-8") as f:
        f.write(
            f"# Application Kit — {company_name}: {title}\n\n"
            f"- Location: {location}\n- Apply: {apply_url}\n"
            f"- Role lens: {rtype}\n- Generated: {datetime.datetime.now():%Y-%m-%d %H:%M}\n"
            f"- Resume PDF: {os.path.basename(pdf_path) if pdf_path else '(render failed)'}\n\n"
            f"## Fit & Advice\n{fit}\n\n## Gaps\n{gaps}\n\n---\n\n{referral_md}\n"
        )

    print(f"  [kit] {company_name} - {title}  ->  {os.path.basename(pdf_path or md_path)}")
    return {"pdf_path": pdf_path, "md_path": md_path, "fit": fit, "gaps": gaps,
            "title": title, "apply_url": apply_url, "message": message}
