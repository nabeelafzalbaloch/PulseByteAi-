"""
make_thumbnail.py
-----------------
Video me se ek frame le kar uspe bara bold title likh kar 1280x720 thumbnail
banata hai (YouTube ke liye). PIL + ffmpeg.

make_thumbnail(video_path, title, out_path) -> out_path
"""

import os
import subprocess
import textwrap
from PIL import Image, ImageDraw, ImageFont, ImageEnhance

FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
W, H = 1280, 720


def _grab_frame(video_path, out_img, at="00:00:02"):
    subprocess.run(["ffmpeg", "-y", "-ss", at, "-i", video_path,
                    "-frames:v", "1", "-q:v", "2", out_img],
                   check=True, capture_output=True)
    return out_img


def _fit_cover(img, w, h):
    iw, ih = img.size
    scale = max(w / iw, h / ih)
    img = img.resize((int(iw * scale), int(ih * scale)), Image.LANCZOS)
    iw, ih = img.size
    left, top = (iw - w) // 2, (ih - h) // 2
    return img.crop((left, top, left + w, top + h))


def make_thumbnail(video_path, title, out_path="thumb.jpg", at="00:00:02"):
    tmp = out_path + ".frame.jpg"
    try:
        _grab_frame(video_path, tmp, at)
        base = Image.open(tmp).convert("RGB")
    except Exception:
        base = Image.new("RGB", (W, H), (15, 18, 30))

    base = _fit_cover(base, W, H)
    base = ImageEnhance.Brightness(base).enhance(0.55)   # darken for text
    draw = ImageDraw.Draw(base)

    # bottom dark band
    band = Image.new("RGBA", (W, 260), (0, 0, 0, 150))
    base.paste(Image.alpha_composite(
        base.crop((0, H - 260, W, H)).convert("RGBA"), band).convert("RGB"),
        (0, H - 260))

    # title: wrap + auto-fit
    title = (title or "").strip().upper()
    size = 86
    while size > 40:
        font = ImageFont.truetype(FONT_BOLD, size)
        wrapped = textwrap.fill(title, width=max(12, int(W / (size * 0.62) * 1.0)))
        bbox = draw.multiline_textbbox((0, 0), wrapped, font=font, spacing=10)
        if bbox[3] - bbox[1] <= 360 and bbox[2] - bbox[0] <= W - 120:
            break
        size -= 6

    font = ImageFont.truetype(FONT_BOLD, size)
    wrapped = textwrap.fill(title, width=max(12, int(W / (size * 0.62))))
    bbox = draw.multiline_textbbox((0, 0), wrapped, font=font, spacing=10)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = (W - tw) // 2
    y = H - th - 80
    draw.multiline_text((x, y), wrapped, font=font, fill=(255, 255, 255),
                        stroke_width=6, stroke_fill=(0, 0, 0),
                        align="center", spacing=10)

    # accent bar
    draw.rectangle([(0, 0), (W, 12)], fill=(229, 57, 53))

    base.save(out_path, "JPEG", quality=88)
    try:
        os.remove(tmp)
    except OSError:
        pass
    return out_path


if __name__ == "__main__":
    make_thumbnail("longvid.mp4", "How AI Will Change The World By 2030", "thumb.jpg")
    print("Done -> thumb.jpg")
