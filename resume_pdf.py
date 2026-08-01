"""
resume_pdf.py  --  render a structured resume (dict) into a clean, ATS-friendly
one-column PDF that mirrors Aditi's existing resume layout.

The tailoring step (tailor_resume.py) produces the structured `data`; this file
just draws it. Keeping layout here (fixed) and content there (tailored) means
every generated PDF looks consistent and professional.
"""

from fpdf import FPDF

# fpdf core fonts are latin-1 only; normalise fancy characters so nothing breaks.
_REPLACINGS = {
    "–": "-", "—": "-", "‘": "'", "’": "'",
    "“": '"', "”": '"', "→": "->", "™": "(TM)",
    "₹": "Rs.", "•": "-", "…": "...", " ": " ",
    "✅": "", "⚠": "",
}


def _ascii(text):
    if text is None:
        return ""
    s = str(text)
    for k, v in _REPLACINGS.items():
        s = s.replace(k, v)
    return s.encode("latin-1", "replace").decode("latin-1")


class _Resume(FPDF):
    def header(self):
        pass

    def footer(self):
        pass


def _section(pdf, title):
    pdf.ln(1.5)
    pdf.set_font("Times", "B", 11.5)
    pdf.cell(0, 5.5, _ascii(title).upper(), new_x="LMARGIN", new_y="NEXT")
    y = pdf.get_y()
    pdf.set_line_width(0.3)
    pdf.line(pdf.l_margin, y, pdf.w - pdf.r_margin, y)
    pdf.ln(1.2)


def _row(pdf, left, right):
    """Bold left text + right-aligned (dates) on one line."""
    epw = pdf.w - pdf.l_margin - pdf.r_margin
    pdf.set_font("Times", "B", 10.5)
    pdf.cell(epw * 0.70, 5, _ascii(left), align="L")
    pdf.set_font("Times", "", 9.5)
    pdf.cell(epw * 0.30, 5, _ascii(right), align="R", new_x="LMARGIN", new_y="NEXT")


def _subtitle(pdf, text):
    if not text:
        return
    pdf.set_font("Times", "I", 10)
    pdf.cell(0, 4.6, _ascii(text), new_x="LMARGIN", new_y="NEXT")


def _bullets(pdf, bullets):
    pdf.set_font("Times", "", 10)
    epw = pdf.w - pdf.l_margin - pdf.r_margin
    for b in bullets or []:
        x0 = pdf.l_margin
        pdf.set_x(x0 + 2)
        pdf.multi_cell(epw - 2, 4.7, _ascii("-  " + b))
    pdf.ln(0.5)


def render_resume(data, out_path):
    """Render the structured resume dict to a PDF at out_path."""
    pdf = _Resume(format="A4")
    pdf.set_auto_page_break(auto=True, margin=12)
    pdf.set_margins(15, 12, 15)
    pdf.add_page()

    # ---- Name + contact ----
    pdf.set_font("Times", "B", 20)
    pdf.cell(0, 9, _ascii(data.get("name", "")), align="C", new_x="LMARGIN", new_y="NEXT")

    contact = data.get("contact", "")
    links = data.get("links", [])
    line2 = " | ".join([p for p in ([contact] + (links or [])) if p])
    if line2:
        pdf.set_font("Times", "", 9.5)
        pdf.cell(0, 4.8, _ascii(line2), align="C", new_x="LMARGIN", new_y="NEXT")

    # ---- Education ----
    edu = data.get("education", [])
    if edu:
        _section(pdf, "Education")
        for e in edu:
            _row(pdf, e.get("institute", ""), e.get("dates", ""))
            detail = " ".join(x for x in [e.get("detail", ""), e.get("note", "")] if x)
            _subtitle(pdf, detail)

    # ---- Experience ----
    exp = data.get("experience", [])
    if exp:
        _section(pdf, "Work Experience")
        for x in exp:
            org_role = " | ".join(p for p in [x.get("org", ""), x.get("role", "")] if p)
            _row(pdf, org_role, x.get("dates", ""))
            _bullets(pdf, x.get("bullets", []))

    # ---- Projects ----
    proj = data.get("projects", [])
    if proj:
        _section(pdf, "Projects")
        for p in proj:
            _row(pdf, p.get("name", ""), p.get("tech", ""))
            _bullets(pdf, p.get("bullets", []))

    # ---- Skills ----
    skills = data.get("skills", {})
    if skills:
        _section(pdf, "Skills")
        for cat, val in skills.items():
            value = val if isinstance(val, str) else ", ".join(val)
            pdf.set_x(pdf.l_margin)
            pdf.set_font("Times", "B", 10)
            pdf.write(4.9, _ascii(f"{cat}: "))   # write() flows + wraps + mixes fonts
            pdf.set_font("Times", "", 10)
            pdf.write(4.9, _ascii(value))
            pdf.ln(5.2)

    # ---- Certifications ----
    certs = data.get("certifications", [])
    if certs:
        _section(pdf, "Certifications")
        _bullets(pdf, certs)

    # ---- Achievements ----
    ach = data.get("achievements", [])
    if ach:
        _section(pdf, "Achievements")
        _bullets(pdf, ach)

    pdf.output(out_path)
    return out_path


if __name__ == "__main__":
    # Quick self-test with a small sample.
    sample = {
        "name": "Aditi",
        "contact": "+91-9817802066 | aditi.17204@gmail.com",
        "links": ["LinkedIn", "GitHub", "Portfolio"],
        "education": [{"institute": "Thapar Institute of Engineering and Technology",
                       "detail": "B.E. Electronics and Computer Engineering", "dates": "Sep 2022 - Present",
                       "note": "CGPA: 9.23/10.0"}],
        "experience": [{"org": "ZS Associates", "role": "BTSA Intern", "dates": "Feb 2026 - Present",
                        "bullets": ["Built ETL pipelines using PySpark & SQL on Azure Databricks.",
                                    "Automated workflows via AI-driven agents, cutting effort 15-20%."]}],
        "projects": [{"name": "PayCraft", "tech": "React, Node.js, ExcelJS",
                      "bullets": ["Reduced payroll processing time by 95% via .xlsx automation."]}],
        "skills": {"Programming Languages": "C++, Python, JavaScript, TypeScript, SQL",
                   "Frameworks": "React, Node.js, Express.js, FastAPI, Spring Boot"},
        "achievements": ["Merit Scholarship for three consecutive years (2022-2025)."],
    }
    out = render_resume(sample, "resume_sample.pdf")
    print("Wrote", out)