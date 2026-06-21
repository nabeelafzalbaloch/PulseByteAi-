"""
telegram_bot.py  (Step 5 + HeyGen avatar test)
----------------------------------------------
Commands:
    script: <topic>   -> text script
    voice:  <topic>   -> script + voiceover mp3
    video:  <topic>   -> poori faceless video
    avatar: <text>    -> HeyGen avatar test (text ko avatar bulwaata hai)   <-- naya
    (koi aur)         -> alive

Env vars (Railway Variables):
    TELEGRAM_TOKEN, ANTHROPIC_API_KEY, ELEVENLABS_API_KEY, PEXELS_API_KEY
    HEYGEN_API_KEY    (naya -- avatar test ke liye)
"""

import os
import time
import requests
from generate_script import generate_script
from make_voice import make_voiceover
from render_faceless import render_faceless_segment
from render_heygen import make_avatar_test, list_avatars

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
            "PulseByte\n\n"
            "  script: <topic>  -> text script\n"
            "  voice: <topic>   -> script + voiceover\n"
            "  video: <topic>   -> faceless video\n"
            "  avatar: <text>   -> HeyGen avatar test\n\n"
            "Misal:  avatar: Hello, this is a test")
        return

    # --- HeyGen avatars list ---
    if low.strip() in ("avatars", "/avatars"):
        try:
            send_message(chat_id, list_avatars())
        except Exception as e:
            send_message(chat_id, f"❌ Avatars list error: {e}")
        return

    # --- HeyGen avatar test ---
    if low.startswith("avatar:"):
        say = text.split(":", 1)[1].strip()
        if not say:
            send_message(chat_id, "Text khaali hai. Misal: avatar: Hello world")
            return
        send_message(chat_id, "⏳ HeyGen avatar bana raha hoon... (1-2 min)")
        try:
            out = f"heygen_{chat_id}_{int(time.time())}.mp4"
            make_avatar_test(say, out)
            send_video(chat_id, out, caption="HeyGen avatar test ✅")
            try:
                os.remove(out)
            except OSError:
                pass
        except Exception as e:
            send_message(chat_id, f"❌ HeyGen error: {e}")
        return

    # --- script / voice / video ---
    cmd = None
    for c in ("video:", "voice:", "script:"):
        if low.startswith(c):
            cmd = c[:-1]
            break
    if not cmd:
        send_message(chat_id, "✅ PulseByte alive! 'avatar: <text>' ya 'video: <topic>' try karein.")
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

        send_message(chat_id, "🎬 Video render ho rahi hai... (2-3 min)")
        out = f"video_{chat_id}_{int(time.time())}.mp4"
        seg = {"keywords": _keywords_from(data), "text": data["script"]}
        render_faceless_segment(seg, audio, out)
        caption = (data.get("caption", "") + "\n# " + " ".join(data.get("hashtags", [])))
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
    print("PulseByte (Step 5 + HeyGen) bot chal raha hai...")
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
    
