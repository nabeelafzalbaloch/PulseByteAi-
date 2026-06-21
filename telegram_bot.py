"""
telegram_bot.py  (STEP 5 — faceless video)
------------------------------------------
Ab bot poori FACELESS video banata hai: script + voiceover + Pexels b-roll +
auto-captions -> ek 9:16 mp4.

Commands:
    script: <topic>   -> text script
    voice:  <topic>   -> script + voiceover mp3
    video:  <topic>   -> poori faceless video (mp4)   <-- naya
    (koi aur)         -> alive

Env vars (Railway Variables):
    TELEGRAM_TOKEN, ANTHROPIC_API_KEY, ELEVENLABS_API_KEY  (pehle se)
    PEXELS_API_KEY                                         (naya)
    BRAND_VOICE, WHISPER_MODEL, FFMPEG_PRESET              (optional)
"""

import os
import time
import requests
from generate_script import generate_script
from make_voice import make_voiceover
from render_faceless import render_faceless_segment

TOKEN = os.environ.get("TELEGRAM_TOKEN")
BASE = f"https://api.telegram.org/bot{TOKEN}"


def send_message(chat_id, text):
    requests.post(f"{BASE}/sendMessage", data={"chat_id": chat_id, "text": text[:4000]})


def send_audio(chat_id, path, caption=""):
    with open(path, "rb") as f:
        requests.post(f"{BASE}/sendAudio",
                      data={"chat_id": chat_id, "caption": caption[:1000]},
                      files={"audio": f}, timeout=120)


def send_video(chat_id, path, caption=""):
    with open(path, "rb") as f:
        requests.post(f"{BASE}/sendVideo",
                      data={"chat_id": chat_id, "caption": caption[:1000]},
                      files={"video": f}, timeout=600)


def _keywords_from(data):
    """Scenes se saare keywords jama karo (dedup)."""
    kws = []
    for sc in data.get("scenes", []):
        for k in sc.get("keywords", []):
            if k and k not in kws:
                kws.append(k)
    return kws[:8]


def handle(chat_id, text):
    low = text.strip().lower()

    if low in ("/start", "help", "/help"):
        send_message(chat_id,
            "PulseByte (Step 5)\n\n"
            "  script: <topic>  -> text script\n"
            "  voice: <topic>   -> script + voiceover\n"
            "  video: <topic>   -> poori faceless video\n\n"
            "Misal:  video: 3 morning habits")
        return

    cmd = None
    for c in ("video:", "voice:", "script:"):
        if low.startswith(c):
            cmd = c[:-1]
            break
    if not cmd:
        send_message(chat_id, "✅ PulseByte alive! 'video: <topic>' try karein.")
        return

    topic = text.split(":", 1)[1].strip()
    if not topic:
        send_message(chat_id, "Topic khaali hai.")
        return

    send_message(chat_id, f"⏳ Script bana raha hoon: \"{topic}\"...")
    try:
        data = generate_script(topic, duration=30)
        send_message(chat_id,
            f"🎯 HOOK ({data.get('hook_type','?')}):\n{data['hook']}\n\n"
            f"📝 {data['script']}")

        if cmd == "script":
            return

        send_message(chat_id, "🎙️ Awaaz bana raha hoon...")
        audio = f"audio_{chat_id}_{int(time.time())}.mp3"
        make_voiceover(data["script"], audio)

        if cmd == "voice":
            send_audio(chat_id, audio)
            os.remove(audio)
            return

        # cmd == "video"
        send_message(chat_id, "🎬 Video render ho rahi hai... (2-3 min lag sakte hain)")
        out = f"video_{chat_id}_{int(time.time())}.mp4"
        seg = {"keywords": _keywords_from(data), "text": data["script"]}
        render_faceless_segment(seg, audio, out)

        caption = (data.get("caption", "") + "\n# " +
                   " ".join(data.get("hashtags", [])))
        send_video(chat_id, out, caption)

        for f in (audio, out):
            try:
                os.remove(f)
            except OSError:
                pass

    except Exception as e:
        send_message(chat_id, f"❌ Error: {e}")


def main():
    if not TOKEN:
        raise SystemExit("TELEGRAM_TOKEN set nahi hai.")
    for k in ("ANTHROPIC_API_KEY", "ELEVENLABS_API_KEY", "PEXELS_API_KEY"):
        if not os.environ.get(k):
            print(f"WARNING: {k} set nahi.")

    print("PulseByte Step 5 bot chal raha hai...")
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
    
