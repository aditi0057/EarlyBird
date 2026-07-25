"""
approvals.py  --  builds a kit ONLY when you tap "Make Kit" on your phone.

HOW IT FITS TOGETHER:
  - The monitor (fetch_jobs.py) alerts you to new roles with a "Make Kit" button
    and records each as pending (pending.json).
  - Tapping the button POSTs the role's id to your ntfy approve-topic.
  - This script (run every ~5 min by the "JobKitBuilder" scheduled task) polls
    that approve-topic, and for each tapped role builds the tailored resume PDF +
    referral drafts, then pushes the PDF (+ a copyable referral message) to you.

So kits are built only on demand — no wasted storage or API calls.
"""

import os
import sys
import json
import time
import datetime
import requests
import truststore
truststore.inject_into_ssl()

# Don't build more than this many kits in a single poll (protects Gemini quota
# and ntfy rate limits). Extra approvals are handled on the next 5-min run.
MAX_BUILDS_PER_RUN = 6

# --- logging to approvals.log (background runs have no console) ---
_LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "approvals.log")
_lf = open(_LOG, "a", encoding="utf-8", buffering=1)


class _Tee:
    def __init__(self, *s): self.streams = [x for x in s if x is not None]
    def write(self, d):
        for s in self.streams:
            try: s.write(d)
            except (ValueError, OSError): pass
    def flush(self):
        for s in self.streams:
            try: s.flush()
            except (ValueError, OSError): pass


_con = sys.stdout
if _con is not None:
    try: _con.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError): _con = None
sys.stdout = _Tee(_con, _lf)
sys.stderr = sys.stdout

from notify import load_config, approve_topic, send_attachment, send_push
from kit import build_full_kit

HERE = os.path.dirname(os.path.abspath(__file__))
PENDING_FILE = os.path.join(HERE, "pending.json")
STATE_FILE = os.path.join(HERE, "approve_state.json")


def _load(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return default


def _save(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2)


def _oneline(text, limit=180):
    return " ".join(str(text or "").split())[:limit]


def poll_approvals(topic, since):
    url = f"https://ntfy.sh/{topic}/json?poll=1&since={since}"
    r = requests.get(url, timeout=25)
    r.raise_for_status()
    out = []
    for line in r.text.splitlines():
        if not line.strip():
            continue
        try:
            m = json.loads(line)
        except json.JSONDecodeError:
            continue
        if m.get("event") == "message":
            out.append((int(m.get("time", 0)), (m.get("message") or "").strip()))
    return out


def main():
    print(f"\n===== Approvals check: {datetime.datetime.now():%Y-%m-%d %H:%M:%S} =====")
    cfg = load_config()
    if not cfg.get("ntfy_topic"):
        print("  No ntfy topic configured.")
        return

    topic = approve_topic()
    state = _load(STATE_FILE, {"last_ts": 0, "processed": []})
    since = state["last_ts"] if state.get("last_ts") else "12h"

    try:
        msgs = poll_approvals(topic, since)
    except requests.RequestException as e:
        print(f"  Could not poll approvals: {e}")
        return

    if not msgs:
        print("  No approvals waiting.")
        return

    pending = _load(PENDING_FILE, {})
    processed = set(state.get("processed", []))
    last_ts = state.get("last_ts", 0)
    built = 0

    for ts, sid in sorted(msgs, key=lambda m: m[0]):  # oldest first
        if built >= MAX_BUILDS_PER_RUN:
            print(f"  Reached per-run cap ({MAX_BUILDS_PER_RUN}); the rest run next time.")
            break
        last_ts = max(last_ts, ts)  # only advanced for messages we actually consume
        if not sid or sid in processed:
            continue
        processed.add(sid)
        entry = pending.get(sid)
        if not entry:
            print(f"  Approval '{sid}': not in pending (expired/already built). Skipping.")
            continue

        company = entry.get("company", "")
        print(f"  Building kit for: {company} (id {sid}) ...")
        kit = build_full_kit(company, entry.get("job", {}), entry.get("role_type", "tech"), cfg)
        if not kit:
            send_push(f"Sorry — couldn't build the kit for {company}. Open the role link directly.")
            continue

        built += 1
        title = kit.get("title", "")
        summary = f"Fit: {_oneline(kit.get('fit'), 140)} | Gaps: {_oneline(kit.get('gaps'), 80)}"
        if kit.get("pdf_path"):
            send_attachment(kit["pdf_path"], f"Kit ready: {company} - {title}", summary)
        time.sleep(1)  # be gentle with ntfy rate limits
        send_push(f"Referral message for {company} - {title} (fill [Name]):\n\n{kit.get('message','')}")
        time.sleep(1)
        pending.pop(sid, None)

    state["last_ts"] = last_ts + 1
    state["processed"] = list(processed)[-500:]
    _save(STATE_FILE, state)
    _save(PENDING_FILE, pending)
    print(f"  Built {built} kit(s).")


if __name__ == "__main__":
    main()
