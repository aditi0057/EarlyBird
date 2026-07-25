"""
notify.py  --  sends new-job alerts to your phone via ntfy.sh (push notifications).

WHY ntfy.sh (and not Telegram):
  Your work network (Zscaler) blocks Telegram. ntfy.sh is a free, open push
  service that IS reachable, needs no account and no token, and pushes straight
  to your phone. You just subscribe your phone to a secret "topic" once.

HOW IT WORKS:
  The script POSTs your alert text to  https://ntfy.sh/<your-topic>
  Your phone, subscribed to that same topic in the ntfy app, gets a push.

SETUP (one time, ~2 minutes):
  1. Install the "ntfy" app (Google Play / App Store).
  2. Open it -> tap "+" (Subscribe to topic) -> type your topic EXACTLY as it
     appears in config.local.json under "ntfy_topic" -> Subscribe.
  3. Done. Every alert now pushes to your phone.

PRIVACY NOTE:
  ntfy topics are public to anyone who knows the name. Yours is a long random
  string so it's effectively private -- just don't share it.

If config.local.json has no "ntfy_topic", notifications are skipped (the script
still prints to the terminal as normal), so nothing breaks.
"""

import os
import json
import requests
import truststore
truststore.inject_into_ssl()

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.local.json")

NTFY_URL = "https://ntfy.sh/{topic}"


# Environment variables override config.local.json. This is what lets the app
# run on a server (GitHub Actions) using SECRETS instead of a local file.
_ENV_MAP = {
    "GEMINI_API_KEY": "gemini_api_key",
    "GEMINI_MODEL": "gemini_model",
    "NTFY_TOPIC": "ntfy_topic",
    "APPROVE_TOPIC": "approve_topic",
    "RESUME_LINK": "resume_link",
    "YOUR_NAME": "your_name",
    "SCHOOL": "school",
}


def load_config():
    """Settings from config.local.json, with environment variables taking
    precedence (so cloud deployments use secrets, local runs use the file)."""
    cfg = {}
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8-sig") as f:
                cfg = json.load(f)
        except (json.JSONDecodeError, OSError):
            cfg = {}
    for env_key, cfg_key in _ENV_MAP.items():
        val = os.environ.get(env_key)
        if val:
            cfg[cfg_key] = val
    return cfg


def is_configured():
    """True if we have somewhere to send alerts."""
    cfg = load_config()
    return bool(cfg.get("ntfy_topic"))


def approve_topic():
    """The ntfy topic the phone posts to when you tap 'Make Kit'."""
    cfg = load_config()
    return cfg.get("approve_topic") or (cfg.get("ntfy_topic", "") + "-approve")


def send_push_actions(title, message, actions):
    """Publish a push with tappable action buttons (JSON publish). Returns True on success.
    `actions` is a list of ntfy action dicts."""
    cfg = load_config()
    topic = cfg.get("ntfy_topic")
    if not topic:
        return False
    payload = {
        "topic": topic,
        "title": title,
        "message": message,
        "markdown": True,
        "tags": ["briefcase"],
        "actions": actions,
    }
    try:
        r = requests.post("https://ntfy.sh", data=json.dumps(payload).encode("utf-8"), timeout=20)
        r.raise_for_status()
        return True
    except requests.RequestException as error:
        print(f"  [!] ntfy action push failed: {error}")
        return False


def send_attachment(file_path, title, message):
    """Push a notification with a file attached (e.g. the tailored resume PDF)."""
    cfg = load_config()
    topic = cfg.get("ntfy_topic")
    if not topic:
        return False
    import os
    filename = os.path.basename(file_path)
    try:
        with open(file_path, "rb") as f:
            data = f.read()
        r = requests.put(
            f"https://ntfy.sh/{topic}",
            data=data,
            headers={
                "Filename": filename,
                "Title": title.encode("ascii", "replace").decode(),
                "Message": message.encode("ascii", "replace").decode(),
                "Tags": "page_facing_up",
            },
            timeout=30,
        )
        r.raise_for_status()
        return True
    except (requests.RequestException, OSError) as error:
        print(f"  [!] ntfy attachment failed: {error}")
        return False


def send_push(message, title="New job matches"):
    """Send one push notification to your phone via ntfy. Returns True on success."""
    cfg = load_config()
    topic = cfg.get("ntfy_topic")
    if not topic:
        return False

    url = NTFY_URL.format(topic=topic)
    # ntfy takes the notification body as the raw POST data, and optional
    # settings via headers. We ask it to render Markdown so links are tappable.
    headers = {
        "Title": title,
        "Tags": "briefcase",
        "Markdown": "yes",
    }
    try:
        r = requests.post(
            url,
            data=message.encode("utf-8"),
            headers=headers,
            timeout=20,
        )
        r.raise_for_status()
        return True
    except requests.RequestException as error:
        print(f"  [!] ntfy push failed: {error}")
        return False


def _shorten(text, limit):
    """First line/sentence of `text`, trimmed to `limit` chars."""
    if not text:
        return ""
    text = " ".join(text.split())          # collapse whitespace/newlines
    first = text.split(". ")[0]            # roughly the first sentence
    snippet = first if len(first) <= limit else text
    return (snippet[:limit].rstrip() + "…") if len(snippet) > limit else snippet


def format_jobs_message(new_matches, kits=None, key_fn=None):
    """Build a tidy push message from a list of (company, job) tuples.

    If `kits` (a dict job_key -> kit info) and `key_fn` are given, each job also
    shows its fit summary, gaps, and where its application kit was saved.
    Uses Markdown so links are tappable in the ntfy app.
    """
    kits = kits or {}
    lines = [f"**{len(new_matches)} new role(s) matched!**", ""]
    for company_name, job in new_matches:
        title = job.get("title", "Untitled role")
        location = job.get("location", {}).get("name", "")
        link = job.get("absolute_url", "")
        line = f"• **{company_name}** — {title}"
        if location:
            line += f" ({location})"
        lines.append(line)
        if link:
            lines.append(f"  [Apply]({link})")

        kit = kits.get(key_fn(company_name, job)) if key_fn else None
        if kit:
            fit = _shorten(kit.get("fit", ""), 160)
            gaps = _shorten(kit.get("gaps", ""), 120)
            if fit:
                lines.append(f"  💡 {fit}")
            if gaps and gaps.lower() not in ("none obvious.", "none obvious", "none"):
                lines.append(f"  ⚠️ Gaps: {gaps}")
            lines.append(f"  📄 Kit (on your PC → `py open_kit.py`): {kit.get('path', '')}")
        lines.append("")
    return "\n".join(lines)
