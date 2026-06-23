"""
publish_facebook.py
Facebook Page par video post karta hai (Graph API se).
Zaroori env vars:
  FB_PAGE_ID     - aap ke Facebook Page ki ID (number)
  FB_PAGE_TOKEN  - long-lived Page access token
"""

import os
import requests

GRAPH_VERSION = os.environ.get("FB_GRAPH_VERSION", "v21.0")
# Video upload ke liye Facebook ka alag (graph-video) host hota hai
VIDEO_BASE = f"https://graph-video.facebook.com/{GRAPH_VERSION}"
GRAPH_BASE = f"https://graph.facebook.com/{GRAPH_VERSION}"


def _creds(page_id=None, token=None):
    page_id = page_id or os.environ.get("FB_PAGE_ID", "").strip()
    token = token or os.environ.get("FB_PAGE_TOKEN", "").strip()
    return page_id, token


def is_configured():
    page_id, token = _creds()
    return bool(page_id and token)


def post_video(file_path, caption="", page_id=None, token=None, timeout=600):
    """
    Facebook Page par video post karta hai.
    Pehle Reels API (naye pages ke liye), fail ho to purana /videos.
    Return: dict {ok, id?, error?}
    """
    page_id, token = _creds(page_id, token)
    if not page_id or not token:
        return {"ok": False, "error": "FB_PAGE_ID ya FB_PAGE_TOKEN set nahi hai"}
    if not os.path.exists(file_path):
        return {"ok": False, "error": f"file nahi mili: {file_path}"}

    reel = _post_reel(file_path, caption, page_id, token, timeout)
    if reel.get("ok"):
        return reel
    # fallback: purana videos endpoint
    vid = _post_video_classic(file_path, caption, page_id, token, timeout)
    if vid.get("ok"):
        return vid
    # dono fail -> reel error wapas (zyada relevant)
    return reel


def _post_reel(file_path, caption, page_id, token, timeout=600):
    """Facebook Reels API — 3 step (start -> upload -> finish)."""
    try:
        # 1) START
        start = requests.post(
            f"{GRAPH_BASE}/{page_id}/video_reels",
            data={"upload_phase": "start", "access_token": token},
            timeout=60,
        ).json()
        video_id = start.get("video_id")
        upload_url = start.get("upload_url")
        if not video_id or not upload_url:
            return {"ok": False, "error": start.get("error", start)}

        # 2) UPLOAD (binary)
        size = os.path.getsize(file_path)
        with open(file_path, "rb") as f:
            up = requests.post(
                upload_url,
                headers={
                    "Authorization": f"OAuth {token}",
                    "offset": "0",
                    "file_size": str(size),
                },
                data=f.read(),
                timeout=timeout,
            )
        try:
            up_body = up.json()
        except Exception:
            up_body = {"raw": up.text}
        if not up_body.get("success", True) and "error" in up_body:
            return {"ok": False, "error": up_body.get("error")}

        # 3) FINISH (publish)
        fin = requests.post(
            f"{GRAPH_BASE}/{page_id}/video_reels",
            data={
                "upload_phase": "finish",
                "video_id": video_id,
                "video_state": "PUBLISHED",
                "description": caption or "",
                "access_token": token,
            },
            timeout=120,
        ).json()
        if fin.get("success") or fin.get("post_id") or fin.get("id"):
            return {"ok": True, "id": video_id}
        return {"ok": False, "error": fin.get("error", fin)}
    except requests.exceptions.RequestException as e:
        return {"ok": False, "error": f"network error: {e}"}


def _post_video_classic(file_path, caption, page_id, token, timeout=600):
    """Purana /videos endpoint (purane pages ke liye)."""
    url = f"{VIDEO_BASE}/{page_id}/videos"
    data = {"description": caption or "", "access_token": token}
    try:
        with open(file_path, "rb") as f:
            files = {"source": (os.path.basename(file_path), f, "video/mp4")}
            r = requests.post(url, data=data, files=files, timeout=timeout)
        try:
            body = r.json()
        except Exception:
            body = {"raw": r.text}
        if r.status_code == 200 and "id" in body:
            return {"ok": True, "id": body["id"]}
        return {"ok": False, "error": body.get("error", body), "status": r.status_code}
    except requests.exceptions.RequestException as e:
        return {"ok": False, "error": f"network error: {e}"}


def check_token(page_id=None, token=None):
    """Token theek hai ya nahi, jaanchta hai. Return dict."""
    page_id, token = _creds(page_id, token)
    if not page_id or not token:
        return {"ok": False, "error": "FB_PAGE_ID ya FB_PAGE_TOKEN set nahi"}
    try:
        r = requests.get(
            f"{GRAPH_BASE}/{page_id}",
            params={"fields": "name", "access_token": token},
            timeout=30,
        )
        body = r.json()
        if r.status_code == 200 and "name" in body:
            return {"ok": True, "name": body["name"]}
        return {"ok": False, "error": body.get("error", body)}
    except requests.exceptions.RequestException as e:
        return {"ok": False, "error": str(e)}


if __name__ == "__main__":
    # Quick local test: python publish_facebook.py /path/to/video.mp4 "caption"
    import sys
    print("Configured:", is_configured())
    print("Token check:", check_token())
    if len(sys.argv) > 1:
        cap = sys.argv[2] if len(sys.argv) > 2 else "Test post"
        print(post_video(sys.argv[1], cap))
      
