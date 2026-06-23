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
    Facebook Page par ek video upload karta hai.
    Return: dict {ok, id?, error?}
    """
    page_id, token = _creds(page_id, token)
    if not page_id or not token:
        return {"ok": False, "error": "FB_PAGE_ID ya FB_PAGE_TOKEN set nahi hai"}

    if not os.path.exists(file_path):
        return {"ok": False, "error": f"file nahi mili: {file_path}"}

    url = f"{VIDEO_BASE}/{page_id}/videos"
    data = {
        "description": caption or "",
        "access_token": token,
    }
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

        err = body.get("error", {})
        msg = err.get("message") or body
        return {"ok": False, "error": msg, "status": r.status_code}
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
      
