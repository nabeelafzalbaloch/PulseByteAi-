"""
telegram_bot.py  (STEP 2 — smoke test only)
-------------------------------------------
Maqsad: confirm karna ke GitHub -> Railway -> Telegram ka rasta kaam karta hai.
Ye bot sirf har message ka jawab "alive" deta hai. Engine baad me aayega.

Env var chahiye (Railway Variables me): TELEGRAM_TOKEN
"""

import os
import time
import requests

TOKEN = os.environ.get("TELEGRAM_TOKEN")
BASE = f"https://api.telegram.org/bot{TOKEN}"


def send_message(chat_id, text):
    requests.post(f"{BASE}/sendMessage", data={"chat_id": chat_id, "text": text})


def main():
    if not TOKEN:
        raise SystemExit("TELEGRAM_TOKEN set nahi hai (Railway Variables me daalein).")

    print("PulseByte smoke-test bot chal raha hai...")
    offset = None
    while True:
        try:
            r = requests.get(f"{BASE}/getUpdates",
                             params={"timeout": 30, "offset": offset}, timeout=40)
            for update in r.json().get("result", []):
                offset = update["update_id"] + 1
                msg = update.get("message") or {}
                chat_id = (msg.get("chat") or {}).get("id")
                text = msg.get("text", "")
                if chat_id:
                    send_message(chat_id, f"✅ PulseByte alive! Tum ne bheja: \"{text}\"")
        except requests.exceptions.RequestException:
            time.sleep(3)
        except KeyboardInterrupt:
            print("Bot band.")
            break


if __name__ == "__main__":
    main()
