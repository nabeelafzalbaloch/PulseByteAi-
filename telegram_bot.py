"""
telegram_bot.py  (STEP 3 — Claude script engine)
------------------------------------------------
Ab bot Claude se script bana kar deta hai. Video abhi nahi -- pehle confirm ke
"dimaag" (script generation) theek chal raha hai.

Commands:
    script: <topic>   -> Claude se hook + script + caption + hashtags
    (koi aur message) -> alive reply

Env vars (Railway Variables):
    TELEGRAM_TOKEN    (pehle se)
    ANTHROPIC_API_KEY (naya -- is step ke liye)
    BRAND_VOICE       (optional: tone, jaise "punchy, direct, no fluff")
"""

import os
import time
import requests
from generate_script import generate_script

TOKEN = os.environ.get("TELEGRAM_TOKEN")
BASE = f"https://api.telegram.org/bot{TOKEN}"


def send_message(chat_id, text):
    # Telegram ek message me ~4096 chars allow karta hai
    requests.post(f"{BASE}/sendMessage", data={"chat_id": chat_id, "text": text[:4000]})


def handle(chat_id, text):
    low = text.strip().lower()

    if low in ("/start", "help", "/help"):
        send_message(chat_id,
            "PulseByte (Step 3) — Claude script engine.\n\n"
            "Bhejein:\n"
            "  script: <topic>\n\n"
            "Misal:  script: 3 morning habits that boost focus")
        return

    if low.startswith("script:"):
        topic = text.split(":", 1)[1].strip()
        if not topic:
            send_message(chat_id, "Topic khaali hai. Misal: script: morning habits")
            return
        send_message(chat_id, f"⏳ Script bana raha hoon: \"{topic}\"...")
        try:
            data = generate_script(topic, duration=30)
            msg = (
                f"🎯 HOOK ({data.get('hook_type','?')}):\n{data['hook']}\n\n"
                f"📝 SCRIPT:\n{data['script']}\n\n"
                f"💬 CAPTION:\n{data.get('caption','')}\n\n"
                f"# {' '.join(data.get('hashtags', []))}"
            )
            send_message(chat_id, msg)
        except Exception as e:
            send_message(chat_id, f"❌ Error: {e}")
        return

    # baaki sab -> alive
    send_message(chat_id, f"✅ PulseByte alive! 'script: <topic>' bhej kar test karein.")


def main():
    if not TOKEN:
        raise SystemExit("TELEGRAM_TOKEN set nahi hai.")
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("WARNING: ANTHROPIC_API_KEY set nahi -- script command fail karega.")

    print("PulseByte Step 3 bot chal raha hai...")
    offset = None
    while True:
        try:
            r = requests.get(f"{BASE}/getUpdates",
                             params={"timeout": 30, "offset": offset}, timeout=40)
            for update in r.json().get("result", []):
                offset = update["update_id"] + 1
                msg = update.get("message") or {}
                chat_id = (msg.get("chat") or {}).get("id")
                text = msg.get("text")
                if chat_id and text:
                    handle(chat_id, text)
        except requests.exceptions.RequestException:
            time.sleep(3)
        except KeyboardInterrupt:
            print("Bot band.")
            break


if __name__ == "__main__":
    main()
