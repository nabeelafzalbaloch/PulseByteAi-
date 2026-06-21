"""
telegram_bot.py  (PulseByteAi — full + AUTO-SCHEDULER + manual)
--------------------------------------------------------------
Manual commands (Telegram):
    script: <topic>   voice: <topic>   video: <topic>
    post: <topic>     -> video + Telegram + YouTube/TikTok pe post
    autopost          -> abhi ek auto-cycle chalao (test)
    topics            -> topics.txt list
    accounts          -> connected account IDs
    avatar: <text>    avatars

Auto-scheduler (background thread):
    AUTO_POST=on hone par har SCHEDULE_HOURS (default 6) ghante topics.txt se
    agla topic utha kar video banaye + post kare.

Env:
    TELEGRAM_TOKEN, ANTHROPIC_API_KEY, ELEVENLABS_API_KEY, PEXELS_API_KEY,
    ZERNIO_API_KEY, ZERNIO_ACCOUNTS
    AUTO_POST (on/off, default off), SCHEDULE_HOURS (default 6),
    OWNER_CHAT_ID (auto-post notifications yahan aayengी)
"""

import os
import time
import threading
import requests
import schedule
from generate_script import generate_script
from make_voice import make_voiceover
from render_faceless import render_faceless_segment
from render_heygen import make_avatar_test, list_avatars
from publish import publish_video, list_accounts

TOKEN = os.environ.get("TELEGRAM_TOKEN")
BASE = f"https://api.telegram.org/bot{TOKEN}"

AUTO_POST = os.environ.get("AUTO_POST", "off").lower() == "on"
SCHEDULE_HOURS = float(os.environ.get("SCHEDULE_HOURS", "6"))
OWNER_CHAT_ID = os.environ.get("OWNER_CHAT_ID")
TOPICS_FILE = "topics.txt"
STATE_FILE = "topic_state.txt"

# ek waqt me sirf ek video render ho (Railway memory safe)
render_lock = threading.Lock()


def send_message(chat_id, text):
    if not chat_id:
        return
    requests.post(f"{BASE}/sendMessage", data={"chat_id": chat_id, "text": text[:4000]})


def send_audio(chat_id, path, caption=""):
    with open(path, "rb") as f:
        requests.post(f"{BASE}/sendAudio",
                      data={"chat_id": chat_id, "caption": caption[:1000]},
                      files={"audio": f}, timeout=120)


def send_video(chat_id, path, caption=""):
    if not chat_id:
        return
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


def _caption_of(data):
    return (data.get("description", "")[:800] + "\n\n" +
            " ".join(data.get("hashtags", [])))


def _send_breakdown(chat_id, d):
    send_message(chat_id,
        f"\U0001F4CC TITLE ({len(d.get('title',''))} chars):\n{d.get('title','')}\n\n"
        f"\U0001F3AF HOOK ({d.get('hook_type','?')}):\n{d.get('hook','')}\n\n"
        f"\U0001F4DD SCRIPT:\n{d.get('script','')}")
    send_message(chat_id,
        f"\U0001F4C4 DESCRIPTION:\n{d.get('description','')}\n\n"
        f"\U0001F511 KEYWORDS: {', '.join(d.get('keywords', []))}\n"
        f"#\uFE0F\u20E3 {' '.join(d.get('hashtags', []))}\n\n"
        f"\U0001F3AC FLOW NOTES:\n{d.get('video_flow_notes','')}")


def build_video(topic, chat_id=None, tag=""):
    """Script -> voice -> video. (out_path, caption, data). render_lock ke andar."""
    with render_lock:
        data = generate_script(topic, duration=30)
        if chat_id:
            _send_breakdown(chat_id, data)
        audio = f"audio_{tag}{int(time.time())}.mp3"
        make_voiceover(data["script"], audio)
        if chat_id:
            send_message(chat_id, "\U0001F3AC Video render ho rahi hai... (2-3 min)")
        out = f"video_{tag}{int(time.time())}.mp4"
        seg = {"keywords": _keywords_from(data), "text": data["script"]}
        render_faceless_segment(seg, audio, out)
        try:
            os.remove(audio)
        except OSError:
            pass
        return out, _caption_of(data), data


# ---------------- AUTO SCHEDULER ----------------
def _next_topic():
    if not os.path.exists(TOPICS_FILE):
        return None
    with open(TOPICS_FILE) as f:
        topics = [l.strip() for l in f if l.strip()]
    if not topics:
        return None
    idx = 0
    if os.path.exists(STATE_FILE):
        try:
            idx = int(open(STATE_FILE).read().strip())
        except ValueError:
            idx = 0
    topic = topics[idx % len(topics)]
    with open(STATE_FILE, "w") as f:
        f.write(str((idx + 1) % len(topics)))
    return topic


def auto_job():
    topic = _next_topic()
    if not topic:
        print("[scheduler] topics.txt khaali/missing")
        return
    print(f"[scheduler] AUTO topic: {topic}")
    try:
        out, caption, data = build_video(topic, chat_id=None, tag="auto_")
        if OWNER_CHAT_ID:
            send_video(OWNER_CHAT_ID, out, f"[AUTO] {data.get('title','')}\n\n{caption}")
        try:
            publish_video(out, caption)
            print(f"[scheduler] posted: {topic}")
            send_message(OWNER_CHAT_ID, f"\u2705 [AUTO] Posted: {topic}")
        except Exception as e:
            print(f"[scheduler] post fail: {e}")
            send_message(OWNER_CHAT_ID, f"\u26A0\uFE0F [AUTO] post fail: {e}")
        try:
            os.remove(out)
        except OSError:
            pass
    except Exception as e:
        print(f"[scheduler] error: {e}")
        send_message(OWNER_CHAT_ID, f"\u274C [AUTO] error: {e}")


def run_scheduler():
    schedule.every(SCHEDULE_HOURS).hours.do(auto_job)
    print(f"[scheduler] ON: har {SCHEDULE_HOURS} ghante auto-post")
    while True:
        try:
            schedule.run_pending()
        except Exception as e:
            print(f"[scheduler] loop error: {e}")
        time.sleep(30)


# ---------------- TELEGRAM HANDLER ----------------
def handle(chat_id, text):
    low = text.strip().lower()

    if low in ("/start", "help", "/help"):
        send_message(chat_id,
            "PulseByteAi\n\n"
            "  post: <topic>   -> video + YouTube/TikTok pe post\n"
            "  video: <topic>  -> sirf video\n"
            "  script: <topic> / voice: <topic>\n"
            "  autopost        -> abhi ek auto-cycle (test)\n"
            "  topics          -> topic list\n"
            "  accounts        -> account IDs\n"
            "  avatar: <text> / avatars")
        return

    if low in ("topics", "/topics"):
        if os.path.exists(TOPICS_FILE):
            send_message(chat_id, "TOPICS:\n" + open(TOPICS_FILE).read())
        else:
            send_message(chat_id, "topics.txt nahi mili.")
        return

    if low in ("autopost", "/autopost"):
        send_message(chat_id, "\u23F3 Auto-cycle chala raha hoon (ek topic)...")
        threading.Thread(target=auto_job, daemon=True).start()
        return

    if low in ("accounts", "/accounts"):
        try:
            accs = list_accounts()
            if not accs:
                send_message(chat_id, "Koi account connected nahi.")
                return
            lines, env_hint = ["CONNECTED ACCOUNTS:", ""], []
            for a in accs:
                lines.append(f"{a['platform']}  ->  {a['accountId']}  ({a['name']})")
                if a["platform"] and a["accountId"]:
                    env_hint.append(f"{a['platform']}:{a['accountId']}")
            lines += ["", "ZERNIO_ACCOUNTS me ye daalein:", ",".join(env_hint)]
            send_message(chat_id, "\n".join(lines))
        except Exception as e:
            send_message(chat_id, f"\u274C Accounts error: {e}")
        return

    if low in ("avatars", "/avatars"):
        try:
            send_message(chat_id, list_avatars())
        except Exception as e:
            send_message(chat_id, f"\u274C Avatars list error: {e}")
        return

    if low.startswith("avatar:"):
        say = text.split(":", 1)[1].strip()
        if not say:
            send_message(chat_id, "Text khaali hai.")
            return
        send_message(chat_id, "\u23F3 HeyGen avatar bana raha hoon...")
        try:
            out = f"heygen_{chat_id}_{int(time.time())}.mp4"
            make_avatar_test(say, out)
            send_video(chat_id, out, "HeyGen avatar \u2705")
            os.remove(out)
        except Exception as e:
            send_message(chat_id, f"\u274C HeyGen error: {e}")
        return

    if low.startswith("post:"):
        topic = text.split(":", 1)[1].strip()
        if not topic:
            send_message(chat_id, "Topic khaali hai.")
            return
        send_message(chat_id, f"\u23F3 Bana raha hoon: \"{topic}\"...")
        try:
            out, caption, _ = build_video(topic, chat_id=chat_id, tag=f"{chat_id}_")
            send_video(chat_id, out, caption)
            send_message(chat_id, "\U0001F4E4 YouTube/TikTok pe post kar raha hoon...")
            try:
                publish_video(out, caption)
                send_message(chat_id,
                    "\u2705 Post ho gaya!\n"
                    "\U0001F4E5 Facebook ke liye upar wali video download karke daal dein.")
            except Exception as e:
                send_message(chat_id,
                    f"\u26A0\uFE0F Video ban gayi (upar) par auto-post fail: {e}")
            try:
                os.remove(out)
            except OSError:
                pass
        except Exception as e:
            send_message(chat_id, f"\u274C Error: {e}")
        return

    cmd = None
    for c in ("video:", "voice:", "script:"):
        if low.startswith(c):
            cmd = c[:-1]
            break
    if not cmd:
        send_message(chat_id, "\u2705 PulseByteAi alive! 'post: <topic>' try karein.")
        return

    topic = text.split(":", 1)[1].strip()
    if not topic:
        send_message(chat_id, "Topic khaali hai.")
        return
    send_message(chat_id, f"\u23F3 Bana raha hoon: \"{topic}\"...")
    try:
        if cmd == "script":
            with render_lock:
                data = generate_script(topic, duration=30)
            _send_breakdown(chat_id, data)
            return
        if cmd == "voice":
            with render_lock:
                data = generate_script(topic, duration=30)
                _send_breakdown(chat_id, data)
                audio = f"audio_{chat_id}_{int(time.time())}.mp3"
                make_voiceover(data["script"], audio)
            send_audio(chat_id, audio)
            os.remove(audio)
            return
        out, caption, _ = build_video(topic, chat_id=chat_id, tag=f"{chat_id}_")
        send_video(chat_id, out, caption)
        try:
            os.remove(out)
        except OSError:
            pass
    except Exception as e:
        send_message(chat_id, f"\u274C Error: {e}")


def main():
    if not TOKEN:
        raise SystemExit("TELEGRAM_TOKEN set nahi hai.")
    print("PulseByteAi bot chal raha hai...")
    if AUTO_POST:
        threading.Thread(target=run_scheduler, daemon=True).start()
    else:
        print("[scheduler] OFF (AUTO_POST=on karne par chalega)")

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
                    threading.Thread(target=handle, args=(chat_id, text), daemon=True).start()
        except requests.exceptions.RequestException:
            time.sleep(3)
        except KeyboardInterrupt:
            break


if __name__ == "__main__":
    main()
    
