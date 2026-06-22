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
from generate_script import generate_script, generate_rated_script
from make_voice import make_voiceover
from render_faceless import render_faceless_segment, kill_active, reset_cancel
from render_heygen import make_avatar_test, list_avatars
from publish import publish_video, list_accounts, upload_media, create_post
from make_thumbnail import make_thumbnail

TOKEN = os.environ.get("TELEGRAM_TOKEN")
BASE = f"https://api.telegram.org/bot{TOKEN}"

AUTO_POST = os.environ.get("AUTO_POST", "off").lower() == "on"
SCHEDULE_HOURS = float(os.environ.get("SCHEDULE_HOURS", "6"))
AUTO_LONG = os.environ.get("AUTO_LONG", "off").lower() == "on"
LONG_SCHEDULE_HOURS = float(os.environ.get("LONG_SCHEDULE_HOURS", "48"))
OWNER_CHAT_ID = os.environ.get("OWNER_CHAT_ID")
TOPICS_FILE = "topics.txt"
STATE_FILE = "topic_state.txt"
TOPICS_LONG_FILE = "topics_long.txt"
STATE_LONG_FILE = "topic_long_state.txt"
POSTED_FILE = "posted.txt"

# stop switch: set hone par naya kaam nahi, chalti video cancel
STOP = threading.Event()

# ek waqt me sirf ek video render ho (Railway memory safe)
render_lock = threading.Lock()


def _norm(t):
    return (t or "").strip().lower()


def _already_posted(topic):
    if not os.path.exists(POSTED_FILE):
        return False
    with open(POSTED_FILE) as f:
        return _norm(topic) in {_norm(l) for l in f}


def _mark_posted(topic):
    with open(POSTED_FILE, "a") as f:
        f.write(_norm(topic) + "\n")


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
    """Telegram pe video bhejta hai. Fail ho to crash nahi (non-fatal) + 1 retry."""
    if not chat_id:
        return False
    for attempt in range(2):
        try:
            with open(path, "rb") as f:
                r = requests.post(f"{BASE}/sendVideo",
                                  data={"chat_id": chat_id, "caption": caption[:1000]},
                                  files={"video": f}, timeout=900)
            if r.status_code < 400:
                return True
        except Exception as e:
            print(f"[send_video] attempt {attempt+1} fail: {e}")
            time.sleep(3)
    print("[send_video] gave up (post will still continue)")
    return False


def send_photo(chat_id, path, caption=""):
    if not chat_id:
        return
    try:
        with open(path, "rb") as f:
            requests.post(f"{BASE}/sendPhoto",
                          data={"chat_id": chat_id, "caption": caption[:1000]},
                          files={"photo": f}, timeout=180)
    except Exception as e:
        print(f"[send_photo] fail: {e}")


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


def _youtube_only():
    """Long video ke liye sirf youtube account (ZERNIO_ACCOUNTS_LONG ya filter)."""
    explicit = os.environ.get("ZERNIO_ACCOUNTS_LONG")
    if explicit:
        return explicit
    accs = os.environ.get("ZERNIO_ACCOUNTS", "")
    yt = [p.strip() for p in accs.split(",") if p.strip().lower().startswith("youtube:")]
    return ",".join(yt)


def _send_thumb(chat_id, video_path, title):
    """Thumbnail bana kar Telegram pe bhejta hai (non-fatal)."""
    if not chat_id:
        return
    try:
        thumb = f"thumb_{int(time.time())}.jpg"
        make_thumbnail(video_path, title, thumb)
        send_photo(chat_id, thumb,
                   "\U0001F5BC\uFE0F Thumbnail — YouTube Studio me 'custom thumbnail' "
                   "se upload kar dein.")
        try:
            os.remove(thumb)
        except OSError:
            pass
    except Exception as e:
        print(f"[thumb] fail: {e}")


def build_video(topic, chat_id=None, tag="", long_form=False):
    """Script -> self-rate (>=QUALITY_MIN) -> voice -> video. (out, caption, data)."""
    if STOP.is_set():
        raise RuntimeError("Bot ruka hua hai (stop). 'resume' bhejein.")
    with render_lock:
        if STOP.is_set():
            raise RuntimeError("cancelled")
        reset_cancel()   # fresh build, purana cancel hatao
        threshold = float(os.environ.get("QUALITY_MIN", "7"))
        attempts = int(os.environ.get("QUALITY_ATTEMPTS", "3"))
        dur = 300 if long_form else 30
        data, score = generate_rated_script(topic, threshold=threshold,
                                            attempts=attempts, duration=dur,
                                            long_form=long_form)
        print(f"[quality] '{topic}' -> {score}/10")
        if chat_id:
            _send_breakdown(chat_id, data)
            send_message(chat_id, f"\u2B50 Quality score: {score}/10 (min {threshold})")
        if score < threshold:
            fixes = (data.get("_eval") or {}).get("fixes", "")
            raise RuntimeError(
                f"Quality {score}/10 < {threshold} ({attempts} koshish ke baad) — "
                f"video skip ki. Behtari: {fixes[:200]}")
        audio = f"audio_{tag}{int(time.time())}.mp3"
        make_voiceover(data["script"], audio)
        if chat_id:
            send_message(chat_id, "\U0001F3AC Video render ho rahi hai...")
        out = f"video_{tag}{int(time.time())}.mp4"
        seg = {"keywords": _keywords_from(data), "text": data["script"]}
        if long_form:
            long_caps = os.environ.get("LONG_CAPTIONS", "off").lower() == "on"
            render_faceless_segment(seg, audio, out, vertical=False,
                                    max_clip_seconds=6, unique_clips=15,
                                    add_captions=long_caps)
        else:
            render_faceless_segment(seg, audio, out)
        try:
            os.remove(audio)
        except OSError:
            pass
        return out, _caption_of(data), data


# ---------------- AUTO SCHEDULER ----------------
def _next_from(topics_file, state_file):
    if not os.path.exists(topics_file):
        return None
    with open(topics_file) as f:
        topics = [l.strip() for l in f if l.strip()]
    if not topics:
        return None
    idx = 0
    if os.path.exists(state_file):
        try:
            idx = int(open(state_file).read().strip())
        except ValueError:
            idx = 0
    # poori list me se pehla NA-posted topic dhoondo (duplicate se bachao)
    n = len(topics)
    chosen, chosen_idx = None, idx
    for step in range(n):
        i = (idx + step) % n
        if not _already_posted(topics[i]):
            chosen, chosen_idx = topics[i], i
            break
    if chosen is None:
        # sab post ho chuke -> log clear karke dobara cycle shuru
        try:
            os.remove(POSTED_FILE)
        except OSError:
            pass
        chosen, chosen_idx = topics[idx % n], idx % n
    with open(state_file, "w") as f:
        f.write(str((chosen_idx + 1) % n))
    return chosen


def auto_job():
    if STOP.is_set():
        return
    topic = _next_from(TOPICS_FILE, STATE_FILE)
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
            _mark_posted(topic)
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
        if "cancel" not in str(e).lower():
            send_message(OWNER_CHAT_ID, f"\u274C [AUTO] error: {e}")


def auto_long_job():
    if STOP.is_set():
        return
    topic = _next_from(TOPICS_LONG_FILE, STATE_LONG_FILE)
    if not topic:
        print("[long-scheduler] topics_long.txt khaali/missing")
        return
    print(f"[long-scheduler] AUTO LONG topic: {topic}")
    try:
        out, caption, data = build_video(topic, chat_id=None,
                                         tag="autolong_", long_form=True)
        _send_thumb(OWNER_CHAT_ID, out, data.get("title", topic))
        try:
            public_url = upload_media(out)
            create_post(public_url, caption, accounts_env=_youtube_only())
            _mark_posted(topic)
            print(f"[long-scheduler] posted: {topic}")
            send_message(OWNER_CHAT_ID,
                f"\u2705 [AUTO LONG] YouTube pe post: {data.get('title','')}\n\n"
                f"\U0001F4E5 Facebook ke liye download:\n{public_url}")
        except Exception as e:
            print(f"[long-scheduler] post fail: {e}")
            send_message(OWNER_CHAT_ID, f"\u26A0\uFE0F [AUTO LONG] post fail: {e}")
        try:
            os.remove(out)
        except OSError:
            pass
    except Exception as e:
        print(f"[long-scheduler] error: {e}")
        if "cancel" not in str(e).lower():
            send_message(OWNER_CHAT_ID, f"\u274C [AUTO LONG] error: {e}")


def _register_jobs():
    schedule.clear()
    if AUTO_POST and not STOP.is_set():
        schedule.every(SCHEDULE_HOURS).hours.do(auto_job)
        print(f"[scheduler] SHORT ON: har {SCHEDULE_HOURS} ghante")
    if AUTO_LONG and not STOP.is_set():
        schedule.every(LONG_SCHEDULE_HOURS).hours.do(auto_long_job)
        print(f"[scheduler] LONG ON: har {LONG_SCHEDULE_HOURS} ghante")


def run_scheduler():
    _register_jobs()
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
            "  long: <topic>   -> 5-min horizontal video + YouTube (FB manual)\n"
            "  video: <topic>  -> sirf video\n"
            "  script: <topic> / voice: <topic>\n"
            "  autopost        -> abhi ek auto-cycle (test)\n"
            "  autolong        -> abhi ek long auto-cycle (test)\n"
            "  stop            -> sab rok do (chalti video cancel)\n"
            "  resume          -> dobara chalu\n"
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

    if low in ("stop", "/stop", "cancel", "/cancel"):
        STOP.set()
        schedule.clear()
        kill_active()   # chalti hui ffmpeg turant band
        send_message(chat_id,
            "\U0001F6D1 Rok diya. Chalti hui video cancel, auto-posting band.\n"
            "Dobara chalu karne ke liye: resume")
        return

    if low in ("resume", "/resume"):
        STOP.clear()
        reset_cancel()
        _register_jobs()
        send_message(chat_id, "\u25B6\uFE0F Chalu. Auto-posting bahaal (jo on hain).")
        return

    if low in ("autopost", "/autopost"):
        send_message(chat_id, "\u23F3 Auto-cycle chala raha hoon (ek topic)...")
        threading.Thread(target=auto_job, daemon=True).start()
        return

    if low in ("autolong", "/autolong"):
        send_message(chat_id, "\u23F3 Long auto-cycle chala raha hoon (~5 min)...")
        threading.Thread(target=auto_long_job, daemon=True).start()
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

    if low.startswith("long:"):
        topic = text.split(":", 1)[1].strip()
        if not topic:
            send_message(chat_id, "Topic khaali hai.")
            return
        send_message(chat_id,
            f"\u23F3 Long video bana raha hoon (~5 min, thoda waqt lagega): \"{topic}\"...")
        try:
            out, caption, data = build_video(topic, chat_id=chat_id,
                                             tag=f"long_{chat_id}_", long_form=True)
            _send_thumb(chat_id, out, data.get("title", topic))
            send_message(chat_id, "\U0001F4E4 Zernio pe upload + YouTube post...")
            try:
                public_url = upload_media(out)
                create_post(public_url, caption, accounts_env=_youtube_only())
                _mark_posted(topic)
                send_message(chat_id,
                    "\u2705 YouTube pe post ho gaya!\n\n"
                    "\U0001F4E5 Facebook ke liye ye video download karein:\n" + public_url)
            except Exception as e:
                send_message(chat_id, f"\u26A0\uFE0F Post/upload fail: {e}")
            try:
                os.remove(out)
            except OSError:
                pass
        except Exception as e:
            send_message(chat_id, f"\u274C Error: {e}")
        return

    if low.startswith("post:"):
        topic = text.split(":", 1)[1].strip()
        if not topic:
            send_message(chat_id, "Topic khaali hai.")
            return
        if _already_posted(topic):
            send_message(chat_id, "\u2139\uFE0F Ye topic pehle post ho chuka — phir bhi bana raha hoon.")
        send_message(chat_id, f"\u23F3 Bana raha hoon: \"{topic}\"...")
        try:
            out, caption, _ = build_video(topic, chat_id=chat_id, tag=f"{chat_id}_")
            ok = send_video(chat_id, out, caption)
            if not ok:
                send_message(chat_id, "\u2139\uFE0F Telegram pe video bhejne me dikkat (net), "
                                      "par post jaari hai...")
            send_message(chat_id, "\U0001F4E4 YouTube/TikTok pe post kar raha hoon...")
            try:
                publish_video(out, caption)
                _mark_posted(topic)
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


def _drain_old_updates():
    """Startup pe purane (bot down ke dauraan aaye) messages skip kar do."""
    try:
        r = requests.get(f"{BASE}/getUpdates", params={"timeout": 0, "offset": -1}, timeout=20)
        results = r.json().get("result", [])
        if results:
            return results[-1]["update_id"] + 1
    except Exception as e:
        print(f"[startup] drain skip: {e}")
    return None


def main():
    if not TOKEN:
        raise SystemExit("TELEGRAM_TOKEN set nahi hai.")
    print("PulseByteAi bot chal raha hai...")
    i
