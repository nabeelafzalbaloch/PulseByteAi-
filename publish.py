"""
publish.py  (Zernio auto-posting)
---------------------------------
Video ko YouTube/TikTok (jo bhi connected) pe post karta hai.

3 steps: presign -> PUT upload -> create post (publishNow).
Account IDs ke liye list_accounts() use karein.

Env:
    ZERNIO_API_KEY     (sk_...)
    ZERNIO_ACCOUNTS    e.g. "youtube:acc_123,tiktok:acc_456"
"""

import os
import requests

ZERNIO_BASE = "https://zernio.com/api/v1"


def _headers(api_key=None):
    return {"Authorization": f"Bearer {api_key or os.environ.get('ZERNIO_API_KEY')}"}


def list_accounts(api_key=None):
    """Connected accounts ki list: [{accountId, platform, name}]."""
    r = requests.get(f"{ZERNIO_BASE}/accounts", headers=_headers(api_key), timeout=30)
    r.raise_for_status()
    data = r.json()
    accounts = (data.get("accounts") or data.get("data")
                or (data if isinstance(data, list) else []))
    out = []
    for a in accounts:
        out.append({
            "accountId": a.get("_id") or a.get("id") or a.get("accountId"),
            "platform": a.get("platform"),
            "name": a.get("displayName") or a.get("username") or a.get("name") or "",
        })
    return out


def upload_media(file_path, api_key=None, content_type="video/mp4"):
    """presign -> PUT -> publicUrl return."""
    filename = os.path.basename(file_path)
    r = requests.post(
        f"{ZERNIO_BASE}/media/presign",
        headers={**_headers(api_key), "Content-Type": "application/json"},
        json={"filename": filename, "contentType": content_type},
        timeout=40,
    )
    r.raise_for_status()
    pres = r.json()
    upload_url = pres["uploadUrl"]
    public_url = pres["publicUrl"]

    with open(file_path, "rb") as f:
        put = requests.put(upload_url, data=f.read(),
                           headers={"Content-Type": content_type}, timeout=300)
    put.raise_for_status()
    return public_url


def _parse_accounts(env_value):
    """'youtube:acc_1,tiktok:acc_2' -> [{platform, accountId}]."""
    platforms = []
    for pair in (env_value or "").split(","):
        pair = pair.strip()
        if not pair or ":" not in pair:
            continue
        plat, acc = pair.split(":", 1)
        platforms.append({"platform": plat.strip(), "accountId": acc.strip()})
    return platforms


def create_post(public_url, caption, api_key=None, accounts_env=None):
    """Pehle se uploaded media URL ko platforms pe post karta hai."""
    api_key = api_key or os.environ.get("ZERNIO_API_KEY")
    platforms = _parse_accounts(accounts_env or os.environ.get("ZERNIO_ACCOUNTS", ""))
    if not platforms:
        raise RuntimeError("Accounts set nahi (ZERNIO_ACCOUNTS / ZERNIO_ACCOUNTS_LONG).")
    body = {
        "content": caption[:1000],
        "mediaItems": [{"url": public_url, "type": "video"}],
        "platforms": platforms,
        "publishNow": True,
    }
    r = requests.post(
        f"{ZERNIO_BASE}/posts",
        headers={**_headers(api_key), "Content-Type": "application/json"},
        json=body, timeout=120,
    )
    if r.status_code >= 400:
        raise RuntimeError(f"Zernio post failed ({r.status_code}): {r.text[:300]}")
    return r.json()


def publish_video(file_path, caption, api_key=None, accounts_env=None):
    """Video upload + post (publishNow). Zernio response return."""
    api_key = api_key or os.environ.get("ZERNIO_API_KEY")
    public_url = upload_media(file_path, api_key)
    return create_post(public_url, caption, api_key, accounts_env)


if __name__ == "__main__":
    for a in list_accounts():
        print(a)
