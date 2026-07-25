"""
get_chat_id.py  --  one-time helper to find your Telegram CHAT ID.

BEFORE RUNNING:
  1. Put your bot token into config.local.json (telegram_bot_token).
  2. Open Telegram, find your bot, and send it any message (e.g. "hi").

THEN RUN:
  py get_chat_id.py

It prints your chat id. Paste that into config.local.json (telegram_chat_id).
"""

import json
import requests
import truststore
truststore.inject_into_ssl()

from notify import load_config

cfg = load_config()
token = cfg.get("telegram_bot_token")

if not token:
    print("No bot token found. Put it into config.local.json first.")
    raise SystemExit(1)

url = f"https://api.telegram.org/bot{token}/getUpdates"
r = requests.get(url, timeout=20)
data = r.json()

updates = data.get("result", [])
if not updates:
    print("No messages found. Open Telegram, message your bot once, then re-run this.")
    raise SystemExit(1)

# The chat id is in the most recent message.
chat = updates[-1].get("message", {}).get("chat", {})
chat_id = chat.get("id")
name = chat.get("first_name", "")

print(f"\nYour chat id is: {chat_id}   (name: {name})")
print("Paste that into config.local.json under telegram_chat_id.")
