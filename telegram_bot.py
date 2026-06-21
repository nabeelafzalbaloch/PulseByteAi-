"""
telegram_bot.py  (PulseByteAi — full: script/voice/video/avatar + posting)
--------------------------------------------------------------------------
Commands:
    script: <topic>   -> full breakdown
    voice:  <topic>   -> + voiceover
    video:  <topic>   -> faceless video (Telegram pe aati hai)
    post:   <topic>   -> video banaye + Telegram pe bheje (download) + YouTube/TikTok pe post
    accounts          -> connected Zernio accounts ki IDs (ZERNIO_ACCOUNTS ke liye)
    avatar: <text>    -> HeyGen avatar test
    avatars           -> HeyGen avatar list
"""

import os
import time
import requests
from generate_script import generate_script
from make_voice import make_voiceover
from render_faceless import render_faceless_segment
from render_heygen import make_avatar_test, list_avatars
from publish import publish_video, list_accounts

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


def _send_breakdown(chat_id, d):
    send_message(chat_id,
        f"📌 TITLE ({len(d.get('title',''))} chars):\n{d.get('title','')}\n\n"
        f"🎯 HOOK ({d.get('hook_type','?')}):\n{d.get('hook','')}\n\n"
        f"📝 SCRIPT:\n{d.get('script','')}")
    send_message(chat_id,
        f"📄 DESCRIPTION:\n{d.get('description','')}\n\n"
        f"🔑 KEYWORDS: {', '.join(d.get('keywords', []))}\n"
        f"#️⃣ {' '.join(d.get('hashtags', []))}\n\n"
        f"🎬 FLOW NOTES:\n{d.get('video_flow_notes','')}")


def _build_video(chat_id, topic):
    """Script -> voice -> video. (audio_path, out_path, caption) return."""
    data = generate_script(topic, duration=30)
    _send_breakdown(chat_id, data)
    audio = f"audio_{chat_id}_{int(time.time())}.mp3"
    make_voiceover(data["script"], audio)
    send_message(chat_id, "🎬 Video render ho rahi hai... (2-3 min)")
    out = f"video_{chat_id}_{int(time.time())}.mp4"
    seg = {"keywords": _keywords_from(data), "text": data["script"]}
    render_faceless_segment(seg, audio, out)
    caption = (data.get("description", "")[:800] + "\n\n" +
               " ".join(data.get("hashtags", [])))
    return audio, out, caption


def handle(chat_id, text):
    low = text.strip().lower()

    if low in ("/start", "help", "/help"):
        send_message(chat_id,
            "PulseByteAi\n\n"
            "  script: <topic>  -> breakdown\n"
            "  voice: <topic>   -> + voiceover\n"
            "  video: <topic>   -> faceless video\n"
            "  post: <topic>    -> video + YouTube/TikTok pe post\n"
            "  accounts         -> connected account IDs\n"
            "  avatar: <text>   -> HeyGen test\n"
            "  avatars          -> avatar list")
        return

    # --- Zernio accounts list ---
    if low in ("accounts", "/accounts"):
        try:
            accs = list_accounts()
            if not accs:
                send_message(chat_id, "Koi account connected nahi. Zernio dashboard me connect karein.")
                return
            lines = ["CONNECTED ACCOUNTS:", ""]
            env_hint = []
            for a in accs:
                lines.append(f"{a['platform']}  ->  {a['accountId']}  ({a['name']})")
                if a["platform"] and a["accountId"]:
                    env_hint.append(f"{a['platform']}:{a['accountId']}")
            lines += ["", "ZERNIO_ACCOUNTS me ye daalein:", ",".join(env_hint)]
            send_message(chat_id, "\n".join(lines))
        except Exception as e:
            send_message(chat_id, f"❌ Accounts error: {e}")
        return

    # --- HeyGen ---
    if low in ("avatars", "/avatars"):
        try:
            send_message(chat_id, list_avatars())
        except Exception as e:
            send_message(chat_id, f"❌ Avatars list error: {e}")
        return

    if low.startswith("avatar:"):
        say = text.split(":", 1)[1].strip()
        if not say:
            send_message(chat_id, "Text khaali hai.")
            return
        send_message(chat_id, "⏳ HeyGen avatar bana raha hoon... (1-2 min)")
        try:
            out = f"heygen_{chat_id}_{int(time.time())}.mp4"
            make_avatar_test(say, out)
            send_video(chat_id, out, "HeyGen avatar ✅")
            os.remove(out)
        except Exception as e:
            send_message(chat_id, f"❌ HeyGen error: {e}")
        return

    # --- POST: video banaye + Telegram pe bheje + platforms pe post ---
    if low.startswith("post:"):
        topic = text.split(":", 1)[1].strip()
        if not topic:
            send_message(chat_id, "Topic khaali hai.")
            return
        send_message(chat_id, f"⏳ Bana raha hoon: \"{topic}\"...")
        try:
            audio, out, caption = _build_video(chat_id, topic)
            # video pehle Telegram pe (download / Facebook manual ke liye)
            send_video(chat_id, out, caption)
            # phir platforms pe post
            send_message(chat_id, "📤 YouTube/TikTok pe post kar raha hoon...")
            try:
                publish_video(out, caption)
                send_message(chat_id,
                    "✅ Post ho gaya! (connected platforms)\n"
                    "📥 Facebook ke liye upar wali video download karke daal dein.")
            except Exception as e:
                send_message(chat_id,
                    f"⚠️ Video ban gayi (upar download kar lein) par auto-post fail: {e}\n"
                    "Manually upload kar sakte hain.")
            for f in (audio, out):
                try:
                    os.remove(f)
                except OSError:
                    pass
        except Exception as e:
            send_message(chat_id, f"❌ Error: {e}")
        return

    # --- script / voice / video ---
    cmd = None
    for c in ("video:", "voice:", "script:"):
        if low.startswith(c):
            cmd = c[:-1]
            break
    if not cmd:
        send_message(chat_id, "✅ PulseByteAi alive! 'post: <topic>' ya 'video: <topic>' try karein.")
        return

    topic = text.split(":", 1)[1].strip()
    if not topic:
        send_message(chat_id, "Topic khaali hai.")
        return
    send_message(chat_id, f"⏳ Script bana raha hoon: \"{topic}\"...")
    try:
        if cmd == "script":
            data = generate_script(topic, duration=30)
            _send_breakdown(chat_id, data)
            return
        if cmd == "voice":
            data = generate_script(topic, duration=30)
            _send_breakdown(chat_id, data)
            send_message(chat_id, "🎙️ Awaaz bana raha hoon...")
            audio = f"audio_{chat_id}_{int(time.time())}.mp3"
            make_voiceover(data["script"], audio)
            send_audio(chat_id, audio)
            os.remove(audio)
            return
        # video
        audio, out, caption = _build_video(chat_id, topic)
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
    print("PulseByteAi (full + posting) bot chal raha hai...")
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
            break


if __name__ == "__main__":
    main()
                
