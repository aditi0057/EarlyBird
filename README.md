# Job-Hunt Automation — How to Use

A personal system that discovers relevant India software roles across 162 companies,
tailors your resume to each, drafts referral outreach, and pushes it all to your phone.

## How it works (approval-gated — nothing wasted)
Two Windows scheduled tasks, both **windowless** (no command window pops up) and
run while the laptop is on (missed runs catch up on wake):
- **JobMonitor** (2×/day: 8 AM, 6 PM): checks all companies. For each NEW role it
  pushes an alert with a JD-specific **💪 strength** + **⚠️ gaps** line and a
  **✅ Make Kit** button. It does NOT build anything yet.
- **JobKitBuilder** (2×/day: 9 AM, 7 PM): builds kits for the roles you tapped
  "Make Kit" on — a ready-to-apply **resume PDF** + a referral message in your
  style — and pushes them to your phone.

Note: because approvals build 2×/day, a kit you request arrives at the next build
time (9 AM or 7 PM). To get kits faster, increase JobKitBuilder's frequency (it's
windowless, so it won't interrupt you).

So kits (and the heavier AI calls) happen only for roles you choose.

## When a push arrives — your routine
1. Read the **💪 strength** + **⚠️ gaps** on the alert. Mismatch? Ignore it.
2. Worth it? Tap **✅ Make Kit**. (Tap **Open role** to view the posting.)
3. In ~5 min you get: the tailored **resume PDF** (download it) + a **referral
   message** to copy. Also saved on your PC in `kits/` (open with `py open_kit.py`).
4. Apply with the PDF. Send the referral message (open the LinkedIn links in the
   kit `.md`, find a Thapar alum / mid-level engineer, fill `[Name]`, send).
5. Log it in your tracker.

**Note:** set `"resume_link"` in `config.local.json` to your Google Drive resume
link — it's embedded in the referral messages. Free Gemini tier has daily limits;
if you hit them, alerts still send (without strength/gaps) and you can retry kits later.

## Manual commands
| Goal | Command |
|---|---|
| Open newest kit | `py open_kit.py` (or `py open_kit.py list`, `py open_kit.py <name>`) |
| Check now | `Start-ScheduledTask -TaskName JobMonitor` |
| Tailor a pasted JD | put JD in `job.txt`, then `py tailor_resume.py` |
| Tailor a Greenhouse link | `py tailor_resume.py --url "<link>"` |
| Grow companies (GH/Lever/Ashby) | edit `discover_boards.py`, then `py discover_boards.py --append` |
| Add a Workday company | add to `companies.json`: `{"name","source":"workday","token":"tenant:dc:site","type"}` |
| Run history | open `monitor.log` |
| Pause / resume | `Disable-ScheduledTask -TaskName JobMonitor` / `Enable-ScheduledTask -TaskName JobMonitor` |
| Re-baseline (after big company changes) | delete `seen_jobs.json`, then run once |

## Files
- `fetch_jobs.py` — the monitor (discover → filter → tailor → alert)
- `companies.json` — your 162-company watch-list (name, source, token, type)
- `filters.py` — which roles/locations count (tune keywords here)
- `sources.py` — provider adapters (greenhouse/lever/ashby/amazon/workday)
- `tailor_resume.py` — tailoring + archetype voice + quick_assess (alert strength/gaps)
- `resume_pdf.py` — renders the structured resume into a PDF (your layout)
- `kit.py` — builds one job's kit (tailored PDF + referral) on approval
- `approvals.py` — JobKitBuilder: polls your taps, builds + delivers kits
- `referrals.py` — LinkedIn search links + message drafts in your style
- `resume.md` — your master resume (KEEP THIS UPDATED — everything tailors from it)
- `notify.py` — phone push via ntfy (alerts, action buttons, PDF attachments)
- `discover_boards.py` — find/verify new company boards
- `open_kit.py` — open a generated kit PDF
- `config.local.json` — keys, name, school, resume_link, topics (private)
- `pending.json` / `approve_state.json` — approval-flow state (auto-managed)
- `kits/` — generated resume PDFs + kit notes
- `monitor.log` / `approvals.log` — run history

## Deploy always-on (free) — GitHub Actions
Runs in the cloud on a schedule, so it works with your laptop closed/off. Nothing
sensitive lives in the repo — keys come from **GitHub Secrets**, and your real
resume is injected at runtime from a secret (never committed).

**Workflows:** `.github/workflows/monitor.yml` (finds jobs 2×/day) and
`approvals.yml` (builds tapped kits every 30 min). State (`seen_jobs.json`,
`pending.json`, `approve_state.json`) is committed back to the repo between runs.

**Setup:**
1. Create a repo on GitHub (public is fine — secrets stay private).
2. Push this folder (`.gitignore` keeps `config.local.json`, `resume.md`, `.venv`, logs, and `kits/` out).
3. Repo **Settings → Actions → General → Workflow permissions → "Read and write"** (so runs can save state).
4. Repo **Settings → Secrets and variables → Actions → New repository secret**, add:

   | Secret | Value |
   |---|---|
   | `RESUME_MD` | the entire contents of your `resume.md` |
   | `GEMINI_API_KEY` | your Gemini key |
   | `NTFY_TOPIC` | your ntfy topic |
   | `APPROVE_TOPIC` | your ntfy approve-topic |
   | `RESUME_LINK` | your Google Drive resume link |
   | `YOUR_NAME` | e.g. Aditi |
   | `SCHOOL` | e.g. Thapar Institute |
   | `GEMINI_MODEL` | *(optional)* defaults to `gemini-flash-lite-latest` |

5. **Actions** tab → run **Job Monitor** manually (Run workflow) to test → watch your phone.
6. Turn OFF the local scheduled tasks so you're not running in two places:
   `Disable-ScheduledTask -TaskName JobMonitor; Disable-ScheduledTask -TaskName JobKitBuilder`

**Security note (public repo):** never merge pull requests from strangers that touch
`.github/workflows/*` — a malicious workflow change could try to read your secrets.

## Tuning tips
- Getting senior roles? Add words to `EXCLUDE_TITLE_KEYWORDS` in `filters.py`.
- Want more/fewer role types? Edit `ROLE_KEYWORDS` in `filters.py`.
- Update `resume.md` whenever your real resume changes — tailoring is only as good as it.
- Always read the **Gaps** section before applying. Never send an unreviewed resume/message.

## Known limits
- Kits capped at 12 per run (burst protection); extras still alerted.
- Some "Software Engineer" titles are secretly senior — the Gaps/Fit section catches these.
- FAANG/banks vary: Amazon + 21 Workday companies work; Microsoft/Google/Apple/Meta not reachable.
