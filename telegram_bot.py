"""
telegram_bot.py  (STEP 4 — script + voiceover)
----------------------------------------------
Ab bot script ki AWAAZ bhi banata hai (ElevenLabs).

Commands:
    script: <topic>   -> sirf text script (Claude)
    voice:  <topic>   -> script + uska voiceover mp3 (Claude + ElevenLabs)
    (koi aur)         -> alive reply

Env vars (Railway Variables):
    TELEGRAM_TOKEN, ANTHROPIC_API_KEY  (pehle se)
    ELEVENLABS_API_KEY                 (naya -- is step ke liye)
    BRAND_VOICE                        (optional)
"""

import os
import time
import requests
from generate_script import generate_script
from make_voice import make_voiceover

TOKEN = os.environ.get("TELEGRAM_TOKEN")
BASE = f"https://api.telegram.org/bot{TOKEN}"


def send_message(chat_id, text):
    requests.post(f"{BASE}/sendMessage", data={"chat_id": chat_id, "text": text[:4000]})


def send_audio(chat_id, path, caption=""):
    with open(path, "rb") as f:
        requests.post(f"{BASE}/sendAudio",
                      data={"chat_id": chat_id, "caption": caption[:1000]},
                      files={"audio": f}, timeout=120)


def handle(chat_id, text):
    low = text.strip().lower()

    if low in ("/start", "help", "/help"):
        send_message(chat_id,
            "PulseByte (Step 4)\n\n"
            "  script: <topic>  -> text script\n"
            "  voice: <topic>   -> script + voiceover (mp3)\n\n"
            "Misal:  voice: 3 morning habits")
        return

    if low.startswith("script:") or low.startswith("voice:"):
        want_voice = low.startswith("voice:")
        topic = text.split(":", 1)[1].strip()
        if not topic:
            send_message(chat_id, "Topic khaali hai.")
            return

        send_message(chat_id, f"⏳ Script bana raha hoon: \"{topic}\"...")
        try:
            data = generate_script(topic, duration=30)
            msg = (
                f"🎯 HOOK ({data.get('hook_type','?')}):\n{data['hook']}\n\n"
                f"📝 SCRIPT:\n{data['script']}\n\n"
                f"💬 {data.get('caption','')}\n# {' '.join(data.get('hashtags', []))}"
            )
            send_message(chat_id, msg)

            if want_voice:
                send_message(chat_id, "🎙️ Awaaz bana raha hoon...")
                out = f"voice_{chat_id}_{int(time.time())}.mp3"
                result = make_voiceover(data["script"], out)
                dur = result.get("duration")
                send_audio(chat_id, out, caption=f"Voiceover ({dur}s)")
                try:
                    os.remove(out)
                except OSError:
                    pass
        except Exception as e:
            send_message(chat_id, f"❌ Error: {e}")
        return

    send_message(chat_id, "✅ PulseByte alive! 'voice: <topic>' try karein.")


def main():
    if not TOKEN:
        raise SystemExit("TELEGRAM_TOKEN set nahi hai.")
    for k in ("ANTHROPIC_API_KEY", "ELEVENLABS_API_KEY"):
        if not os.environ.get(k):
            print(f"WARNING: {k} set nahi.")

    print("PulseByte Step 4 bot chal raha hai...")
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
            
