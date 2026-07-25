"""
tailor_resume.py  --  tailors your resume to a specific job using Google Gemini.

WHAT IT DOES:
  Reads your master resume (resume.md) + a job description, then asks Gemini to
  re-order and re-phrase YOUR REAL experience to mirror the job — so you clear
  ATS keyword filters — and reports exactly what it changed. It NEVER invents
  experience, skills, or numbers you don't have.

  The monitor (fetch_jobs.py) also imports the functions here to auto-tailor
  every new job it finds. This file can still be run on its own too:

  Way 1 -- paste the job description into  job.txt , then:
     py tailor_resume.py

  Way 2 -- give it a Greenhouse job link directly:
     py tailor_resume.py --url "https://boards.greenhouse.io/databricks/jobs/8564166002"

  The result is written to  tailored_resume.md .

ONE-TIME SETUP:
  Put a free Gemini API key into config.local.json under "gemini_api_key".
"""

import os
import re
import sys
import html
import json
import argparse

import requests
import truststore
truststore.inject_into_ssl()

import json as _json
from google import genai
from google.genai import errors as genai_errors
from google.genai import types as genai_types

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(HERE, "config.local.json")
RESUME_FILE = os.path.join(HERE, "resume.md")
JOB_FILE = os.path.join(HERE, "job.txt")
OUTPUT_FILE = os.path.join(HERE, "tailored_resume.md")

# Free-tier friendly default. Override via config.local.json / GEMINI_MODEL env.
DEFAULT_MODEL = "gemini-flash-lite-latest"

GREENHOUSE_JOB_URL = "https://boards-api.greenhouse.io/v1/boards/{token}/jobs/{job_id}"


def load_config():
    # Single source of truth (file + env overlay) lives in notify.load_config.
    from notify import load_config as _lc
    return _lc()


def read_file(path):
    with open(path, "r", encoding="utf-8-sig") as f:
        return f.read()


def load_resume():
    """Return the master resume text, or None if it's missing."""
    if not os.path.exists(RESUME_FILE):
        return None
    return read_file(RESUME_FILE)


def strip_html(raw):
    """Turn Greenhouse's HTML job content into readable plain text."""
    text = html.unescape(raw or "")
    text = re.sub(r"<\s*br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"</\s*(p|li|div|h\d)\s*>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)          # drop remaining tags
    text = re.sub(r"\n{3,}", "\n\n", text)       # collapse blank lines
    return text.strip()


def fetch_jd_by_token_id(token, job_id):
    """Fetch a Greenhouse job's title + full description text by board token + id."""
    api = GREENHOUSE_JOB_URL.format(token=token, job_id=job_id)
    r = requests.get(api, timeout=20)
    r.raise_for_status()
    data = r.json()
    title = data.get("title", "")
    content = strip_html(data.get("content", ""))
    return f"{title}\n\n{content}"


def fetch_jd_from_greenhouse(url):
    """Given a Greenhouse job URL, fetch the full job description text."""
    token_match = re.search(r"greenhouse\.io/(?:embed/job_app\?for=)?([^/?]+)/jobs/(\d+)", url)
    jid_match = re.search(r"(?:jobs/|gh_jid=)(\d+)", url)
    if not jid_match:
        raise ValueError("Couldn't find a job id in that URL. Use job.txt instead.")
    job_id = jid_match.group(1)
    if not token_match:
        raise ValueError(
            "That looks like a custom careers URL, so I can't auto-fetch it.\n"
            "  Copy the job description text into job.txt and run without --url."
        )
    return fetch_jd_by_token_id(token_match.group(1), job_id)


# The "voice" the resume should take, chosen by the company/role archetype.
LENSES = {
    "tech": (
        "Frame the candidate as a SOFTWARE ENGINEER. Lead with systems design, "
        "scale, performance, code quality, and the specific tech stack from the JD. "
        "Foreground engineering metrics (throughput, reliability, latency, users)."
    ),
    "fintech": (
        "Frame the candidate as a SOFTWARE ENGINEER for a finance/fintech product. "
        "Emphasise reliability, correctness, security, data accuracy, and systems that "
        "handle money or critical data at scale — while keeping strong SWE fundamentals front and centre."
    ),
    "data": (
        "Frame the candidate as a DATA / ML ENGINEER. Lead with data pipelines, ETL, "
        "data scale and accuracy, cloud data platforms (Databricks/Spark/warehouses), "
        "and any ML exposure. Keep general SWE skills as support."
    ),
    "consulting": (
        "Frame the candidate as a CONSULTANT / TECH CONSULTANT. Lead with BUSINESS IMPACT "
        "and outcomes, structured problem-solving, stakeholder and cross-functional "
        "collaboration, and leadership (clubs/teams). Quantify value delivered. Keep "
        "technical depth as an ENABLER of business results, not the headline."
    ),
    "general": "Balance technical depth with clear, quantified impact.",
}


def infer_type(jd_text):
    """Best-guess the archetype from the JD text when none is provided."""
    t = (jd_text or "").lower()
    if any(w in t for w in ("consultant", "consulting", "advisory", "business analyst", "engagement")):
        return "consulting"
    if any(w in t for w in ("trading", "quant", "risk model", "investment bank", "portfolio")):
        return "fintech"
    if any(w in t for w in ("data pipeline", "etl", "spark", "data warehouse", "machine learning model")):
        return "data"
    return "tech"


PROMPT_TEMPLATE = """You are an expert technical resume editor helping a candidate tailor their resume to a specific job so it passes ATS keyword filters AND reads well to a human recruiter.

ROLE LENS (how to FRAME and position this resume for this specific job):
{lens}

ABSOLUTE RULES (do not break these):
- NEVER invent experience, employers, projects, skills, tools, metrics, or dates that are not in the master resume. No fabrication whatsoever.
- You MAY: reorder bullets/skills to surface the most relevant first; rephrase existing bullets to use the job's terminology where it TRUTHFULLY describes what the candidate did; move a genuinely-possessed skill to a more prominent spot; adjust emphasis.
- If the job wants a keyword the candidate does NOT genuinely have, DO NOT add it to the resume. Instead list it under "Gaps".
- Keep it truthful, concise, and one-to-two pages worth of content. Keep the candidate's real numbers.

MASTER RESUME (the only source of truth about the candidate):
---
{resume}
---

JOB DESCRIPTION to tailor toward:
---
{jd}
---

Produce your answer in GitHub-flavored Markdown with EXACTLY these sections, and NO preamble or sign-off text — start your reply directly with the "## Tailored Resume" heading:

## Tailored Resume
(The full tailored resume, same structure as the master, ready to adapt. Reordered/rephrased truthfully for this job.)

## What I Changed and Why
(Bullet list. Each bullet: the change + the reason tied to the JD.)

## JD Keywords You Now Cover
(Comma-separated list of important keywords/skills from the JD that your REAL resume genuinely matches and that now appear.)

## Gaps (keywords the JD wants that you do NOT genuinely have)
(Comma-separated list. Be honest. If none, write "None obvious.")

## Fit & Advice
(2-4 sentences: how strong a fit this role is for the candidate, and one concrete suggestion — e.g. a bullet to strengthen, or whether to prioritize a referral.)
"""


def build_client(cfg):
    """Create a Gemini client from config. Returns (client, model) or raises RuntimeError."""
    api_key = cfg.get("gemini_api_key")
    if not api_key:
        raise RuntimeError("No Gemini API key in config.local.json (gemini_api_key).")
    return genai.Client(api_key=api_key), cfg.get("gemini_model", DEFAULT_MODEL)


def gemini_generate(prompt, cfg):
    """Low-level: send a prompt to Gemini, return the text. Raises on error."""
    client, model = build_client(cfg)
    response = client.models.generate_content(model=model, contents=prompt)
    return (response.text or "").strip()


def generate_tailored(resume_text, jd_text, cfg, role_type=None):
    """Tailor the resume to the JD, framed for the role archetype.

    role_type: "tech" | "fintech" | "data" | "consulting" | None.
    If None (or unknown), the archetype is inferred from the JD text.
    Returns the tailoring Markdown report.
    """
    role_type = (role_type or "").lower()
    if role_type not in LENSES:
        role_type = infer_type(jd_text)
    lens = LENSES.get(role_type, LENSES["general"])
    prompt = PROMPT_TEMPLATE.format(resume=resume_text, jd=jd_text, lens=lens)
    return gemini_generate(prompt, cfg)


def gemini_generate_json(prompt, cfg):
    """Send a prompt to Gemini in JSON mode; return the parsed dict. Raises on error."""
    client, model = build_client(cfg)
    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=genai_types.GenerateContentConfig(response_mime_type="application/json"),
    )
    text = (response.text or "").strip()
    # Strip accidental code fences just in case.
    if text.startswith("```"):
        text = text.strip("`")
        text = text[text.find("{"):]
    return _json.loads(text)


KIT_PROMPT = """You are an expert technical resume editor. Tailor the candidate's resume to a specific job so it passes ATS keyword filters AND reads well, then return STRUCTURED JSON.

ROLE LENS (how to frame/position this resume):
{lens}

ABSOLUTE RULES:
- NEVER invent experience, employers, projects, skills, tools, metrics, or dates not in the master resume. No fabrication.
- You MAY reorder and rephrase existing content to mirror the job's terminology where TRUTHFUL, surface the most relevant items first, and adjust emphasis.
- If the job wants something the candidate genuinely lacks, DO NOT add it to the resume — list it under "gaps".
- Keep it to one page of content. Keep the candidate's real numbers.

MASTER RESUME (only source of truth):
---
{resume}
---

JOB DESCRIPTION:
---
{jd}
---

Return ONLY valid JSON with EXACTLY this shape:
{{
  "resume": {{
    "name": "string",
    "contact": "phone | email",
    "links": ["LinkedIn", "GitHub", "Portfolio"],
    "education": [{{"institute": "", "detail": "", "dates": "", "note": ""}}],
    "experience": [{{"org": "", "role": "", "dates": "", "bullets": ["", ""]}}],
    "projects": [{{"name": "", "tech": "", "bullets": ["", ""]}}],
    "skills": {{"Category Name": "comma-separated values"}},
    "achievements": ["", ""]
  }},
  "fit": "2-3 sentences: how strong a fit, and one concrete tip (e.g. get a referral).",
  "gaps": "comma-separated keywords the JD wants that the candidate does NOT genuinely have; or 'None obvious.'",
  "role_type": "tech|fintech|data|consulting"
}}
Preserve the candidate's exact name, contact, and links from the master resume."""


QUICK_ASSESS_PROMPT = """Compare the candidate's resume to this job. Be honest and SPECIFIC to this job description.

Return JSON: {{"strength": "...", "gaps": "..."}}
- strength: ONE short line naming the candidate's strongest matching point for THIS job (cite something real from the resume).
- gaps: the top 2-3 things THIS job wants that the candidate does NOT genuinely have (comma-separated), or "None obvious.".

RESUME:
---
{resume}
---
JOB:
---
{jd}
---"""


def quick_assess(resume_text, jd_text, cfg):
    """Cheap, JD-specific fit check for alerts. Returns {'strength','gaps'}; empty on failure."""
    prompt = QUICK_ASSESS_PROMPT.format(resume=resume_text, jd=jd_text)
    try:
        data = gemini_generate_json(prompt, cfg)
        return {"strength": data.get("strength", ""), "gaps": data.get("gaps", "")}
    except Exception as e:
        print(f"  [!] quick_assess failed: {e}")
        return {"strength": "", "gaps": ""}


def generate_kit_data(resume_text, jd_text, cfg, role_type=None):
    """Tailor to the JD and return structured data: {resume:{...}, fit, gaps, role_type}."""
    rt = (role_type or "").lower()
    if rt not in LENSES:
        rt = infer_type(jd_text)
    lens = LENSES.get(rt, LENSES["general"])
    prompt = KIT_PROMPT.format(resume=resume_text, jd=jd_text, lens=lens)
    data = gemini_generate_json(prompt, cfg)
    data.setdefault("role_type", rt)
    return data


def extract_section(markdown, heading_contains):
    """Pull one '## ...' section's body out of the tailoring Markdown.

    `heading_contains` is matched case-insensitively against the heading text
    (e.g. "Fit & Advice", "Gaps"). Returns the body text, or "" if not found.
    """
    pattern = re.compile(
        r"^#{1,6}\s*[^\n]*" + re.escape(heading_contains) + r"[^\n]*\n(.*?)(?=^#{1,6}\s|\Z)",
        re.IGNORECASE | re.DOTALL | re.MULTILINE,
    )
    m = pattern.search(markdown or "")
    return m.group(1).strip() if m else ""


def main():
    parser = argparse.ArgumentParser(description="Tailor resume.md to a job using Gemini.")
    parser.add_argument("--url", help="A Greenhouse job URL to auto-fetch the description from.")
    parser.add_argument("--job", default=JOB_FILE, help="Path to a text file with the job description (default: job.txt).")
    args = parser.parse_args()

    cfg = load_config()
    if not cfg.get("gemini_api_key"):
        print("No Gemini API key found.")
        print("  Get a free key at https://aistudio.google.com/apikey and put it")
        print('  into config.local.json under "gemini_api_key".')
        sys.exit(1)

    resume = load_resume()
    if resume is None:
        print(f"Can't find your resume at {RESUME_FILE}.")
        sys.exit(1)

    if args.url:
        print(f"Fetching job description from: {args.url}")
        try:
            jd = fetch_jd_from_greenhouse(args.url)
        except (ValueError, requests.RequestException) as e:
            print(f"  Could not fetch: {e}")
            sys.exit(1)
    else:
        if not os.path.exists(args.job):
            print(f"No job description found. Paste the job text into '{os.path.basename(args.job)}' and run again,")
            print("  or use  --url <greenhouse job link>.")
            sys.exit(1)
        jd = read_file(args.job).strip()
        if len(jd) < 40:
            print(f"'{os.path.basename(args.job)}' looks empty. Paste the full job description into it and re-run.")
            sys.exit(1)

    print(f"Tailoring your resume with {cfg.get('gemini_model', DEFAULT_MODEL)} ... (a few seconds)")
    try:
        output = generate_tailored(resume, jd, cfg)
    except (genai_errors.APIError, RuntimeError) as e:
        print(f"  Gemini error: {e}")
        sys.exit(1)

    if not output:
        print("  Gemini returned an empty response. Try again.")
        sys.exit(1)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(output)

    print("\n" + "=" * 70)
    print(f"  Done! Tailored resume + report written to: {os.path.basename(OUTPUT_FILE)}")
    print("  Review every change, check the 'Gaps' section honestly, then port")
    print("  the good parts into your real resume.")
    print("=" * 70)


if __name__ == "__main__":
    main()
