"""
render_heygen.py  (HeyGen test)
-------------------------------
Sirf ye test karta hai ke HeyGen ka API kaam karta hai ya nahi:
text -> HeyGen avatar talking-head video (HeyGen ki apni voice) -> download.

API v2 (stable). Auth: X-Api-Key header.
    POST /v2/video/generate        -> video_id
    GET  /v1/video_status.get      -> poll -> video_url (status "completed")

Env:
    HEYGEN_API_KEY      (zaroori)
    HEYGEN_AVATAR_ID    (optional, default neeche)
    HEYGEN_VOICE_ID     (optional, default neeche)

Requirements: requests
"""

import os
import time
import requests

GENERATE_URL = "https://api.heygen.com/v2/video/generate"
STATUS_URL = "https://api.heygen.com/v1/video_status.get"

# HeyGen ki documentation ke default stock avatar + voice (test ke liye theek)
DEFAULT_AVATAR = os.environ.get("HEYGEN_AVATAR_ID", "Angela-inTshirt-20220820")
DEFAULT_VOICE = os.environ.get("HEYGEN_VOICE_ID", "1bd001e7e50f421d891986aad5158bc8")


def _headers(api_key):
    return {"X-Api-Key": api_key or os.environ.get("HEYGEN_API_KEY"),
            "Content-Type": "application/json"}


def generate_avatar_video(text, avatar_id=None, voice_id=None, api_key=None, vertical=True):
    """HeyGen pe avatar video ka job submit karta hai, video_id return karta hai."""
    dim = {"width": 720, "height": 1280} if vertical else {"width": 1280, "height": 720}
    payload = {
        "video_inputs": [
            {
                "character": {
                    "type": "avatar",
                    "avatar_id": avatar_id or DEFAULT_AVATAR,
                    "avatar_style": "normal",
                },
                "voice": {
                    "type": "text",
                    "input_text": text,
                    "voice_id": voice_id or DEFAULT_VOICE,
                },
                "background": {"type": "color", "value": "#FAFAFA"},
            }
        ],
        "dimension": dim,
    }
    r = requests.post(GENERATE_URL, headers=_headers(api_key), json=payload, timeout=60)
    data = r.json()
    if data.get("error"):
        raise RuntimeError(f"HeyGen error: {data['error']}")
    return data["data"]["video_id"]


def wait_for_video(video_id, api_key=None, timeout=600, interval=6):
    """Status 'completed' hone tak wait, video_url return karta hai."""
    start = time.time()
    while time.time() - start < timeout:
        r = requests.get(f"{STATUS_URL}?video_id={video_id}",
                         headers={"X-Api-Key": api_key or os.environ.get("HEYGEN_API_KEY"),
                                  "Accept": "application/json"},
                         timeout=30)
        data = r.json().get("data", {})
        status = data.get("status")
        if status == "completed":
            return data["video_url"]
        if status == "failed":
            raise RuntimeError(f"HeyGen render failed: {data.get('error') or data}")
        time.sleep(interval)
    raise TimeoutError("HeyGen render timed out.")


def make_avatar_test(text, output_path="heygen_test.mp4", api_key=None):
    """Pura test: generate -> wait -> download. output_path return karta hai."""
    vid = generate_avatar_video(text, api_key=api_key)
    url = wait_for_video(vid, api_key=api_key)
    resp = requests.get(url, stream=True, timeout=120)
    resp.raise_for_status()
    with open(output_path, "wb") as f:
        for chunk in resp.iter_content(8192):
            f.write(chunk)
    return output_path


if __name__ == "__main__":
    out = make_avatar_test("Hello! This is a HeyGen avatar test for PulseByte.")
    print("Done ->", out)
  
