"""
referrals.py  --  builds a safe referral kit for a company/role.

SAFE BY DESIGN: no LinkedIn automation. It gives you:
  1. Ready-to-CLICK LinkedIn search links (find the right people).
  2. Personalized message DRAFTS in YOUR style — you review, fill [Name], send.

Messages are built from a fixed template (so the format is always right) and
lightly personalised by company, role, and role archetype. Update the wording
or your resume link in config.local.json ("resume_link", "your_name").
"""

import urllib.parse

LINKEDIN_PEOPLE = "https://www.linkedin.com/search/results/people/?keywords={q}{extra}"
NET_FIRST = "&network=%5B%22F%22%5D"
NET_SECOND = "&network=%5B%22S%22%5D"

# Which skills to foreground in the intro, by role archetype (all truthful).
SKILLS_BY_TYPE = {
    "tech": "I'm skilled in Data Structures, AWS, and web development, and proficient in backend development using Spring Boot (Java) and Node.js (JavaScript).",
    "fintech": "I'm skilled in AWS, scalable and reliable backend systems, and data accuracy, and proficient in backend development using Node.js (JavaScript) and Spring Boot (Java).",
    "data": "I'm skilled in PySpark, SQL, and Azure Databricks with hands-on experience building ETL data pipelines, alongside strong backend development in Python and Node.js.",
    "consulting": "I bring strong structured problem-solving and stakeholder-collaboration skills, hands-on experience across data engineering (PySpark, Databricks) and full-stack development, and leadership from heading a 10-member team.",
    "general": "I'm skilled in AWS, web development, and backend engineering using Node.js (JavaScript) and Spring Boot (Java), with data-engineering experience in PySpark and SQL.",
}


def linkedin_links(company_name, school="Thapar Institute"):
    company_q = urllib.parse.quote(company_name)
    alumni_q = urllib.parse.quote(f"{school} {company_name}")
    eng_q = urllib.parse.quote(f"{company_name} software engineer")
    return {
        "connections_at_company": LINKEDIN_PEOPLE.format(q=company_q, extra=NET_FIRST),
        "alumni_at_company": LINKEDIN_PEOPLE.format(q=alumni_q, extra=""),
        "engineers_2nd_degree": LINKEDIN_PEOPLE.format(q=eng_q, extra=NET_SECOND),
    }


def referral_message(company, role, job_link, cfg, role_type="tech"):
    """The main referral-ask message, in Aditi's style."""
    name = cfg.get("your_name", "Aditi")
    resume_link = cfg.get("resume_link") or "[add your resume link in config.local.json]"
    skills = SKILLS_BY_TYPE.get(role_type, SKILLS_BY_TYPE["general"])
    return (
        f"Hello [Name],\n\n"
        f"I'm {name}, a final-year student at Thapar Institute with a strong academic background. "
        f"{skills} I am currently interning at ZS Associates as a BTSA Intern, and previously interned "
        f"at Success Numbers as an SDE Intern and at Schenck Rotec India as an Intern Trainee, gaining "
        f"hands-on experience. I also serve as Joint Secretary of our Economics Club, which has helped "
        f"build my leadership skills.\n\n"
        f"I'm very interested in the {role} role at {company} and would be grateful if you could consider "
        f"referring me, as it would greatly support my application.\n\n"
        f"{job_link}\n\n"
        f"Thank you so much for your time! Here's my resume for reference:\n"
        f"{resume_link}\n\n"
        f"Best,\n{name}"
    )


def connection_note(company, role, cfg):
    """Short LinkedIn connection-request note (<300 chars) for cold 2nd-degree engineers."""
    name = cfg.get("your_name", "Aditi")
    note = (f"Hi [Name], I'm {name}, a final-year Thapar student & SDE intern (React/Node.js/AWS). "
            f"I'm keen on the {role} team at {company} and would love to connect and learn from your journey.")
    return note[:300]


def follow_up(company, role, cfg):
    name = cfg.get("your_name", "Aditi")
    return (f"Hi [Name], just following up on my earlier note about the {role} role at {company}. "
            f"I'd really appreciate any guidance, or a referral if you think I'd be a good fit. Thank you! - {name}")


def build_referral_md(company_name, role_title, job_link, cfg, role_type="tech"):
    """Full referral section (links + all message drafts) as Markdown."""
    school = cfg.get("school", "Thapar Institute")
    links = linkedin_links(company_name, school=school)
    return "\n".join([
        "## Referral outreach",
        "",
        "**Find the right people (open while logged into LinkedIn):**",
        f"- [Your connections at {company_name}]({links['connections_at_company']}) — ask directly.",
        f"- [{school} alumni at {company_name}]({links['alumni_at_company']}) — warmest, highest reply rate.",
        f"- [Engineers at {company_name} to connect with]({links['engineers_2nd_degree']}) — send a note.",
        "",
        "**Target mid-level engineers (2–5 yrs) on/near the team — not recruiters.**",
        "",
        "### Referral message (fill in [Name], then send)",
        "```",
        referral_message(company_name, role_title, job_link, cfg, role_type),
        "```",
        "",
        "### Cold connection-request note (<300 chars)",
        "```",
        connection_note(company_name, role_title, cfg),
        "```",
        "",
        "### Follow-up (if no reply after ~4 days)",
        "```",
        follow_up(company_name, role_title, cfg),
        "```",
    ])
