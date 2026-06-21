"""
render_faceless.py
------------------
Stage 3a: ek FACELESS segment ko render karta hai.
  Input  : segment (text + keywords) + uska voiceover mp3
  Process: Pexels se b-roll clips -> 1080x1920 normalize -> concat
           -> voiceover audio mux -> faster-whisper se auto-captions burn
  Output : ek 9:16 mp4 clip (is segment ki)

Requirements:
    pip install requests faster-whisper
    sudo apt install ffmpeg            # ffmpeg + ffprobe system me hone chahiye
    export PEXELS_API_KEY="..."

Note: faster-whisper pehli dafa model download karega (base ~150MB).
"""

import os
import subprocess
import requests
from faster_whisper import WhisperModel

PEXELS_SEARCH = "https://api.pexels.com/videos/search"
PIXABAY_SEARCH = "https://pixabay.com/api/videos/"
W, H = 1080, 1920

# whisper model: "tiny" fast+sasta (default), "base"/"small" zyada accurate
WHISPER_SIZE = os.environ.get("WHISPER_MODEL", "tiny")
# ffmpeg encode speed: veryfast = kam CPU (Railway $5 ke liye accha)
PRESET = os.environ.get("FFMPEG_PRESET", "veryfast")
# effects: "on" -> crossfade transitions + fade in/out ; "off" -> hard cuts
EFFECTS = os.environ.get("EFFECTS", "on").lower() == "on"
# crossfade transition ki length (seconds)
TRANSITION = float(os.environ.get("TRANSITION", "0.6"))

# Whisper model ek dafa load -> reuse (memory bachta hai)
_WHISPER = None


def _whisper():
    global _WHISPER
    if _WHISPER is None:
        _WHISPER = WhisperModel(WHISPER_SIZE, device="cpu", compute_type="int8")
    return _WHISPER


def _run(cmd):
    """ffmpeg command chalata hai, error pe exception."""
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"ffmpeg failed:\n{res.stderr[-800:]}")


def _media_duration(path):
    """ffprobe se media ki length (seconds)."""
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", path],
        capture_output=True, text=True,
    ).stdout.strip()
    return float(out)


def search_pexels(keywords, api_key=None, per_query=2):
    """Pexels se portrait video clips ke download URLs nikaalta hai."""
    api_key = api_key or os.environ.get("PEXELS_API_KEY")
    if not api_key:
        return []
    headers = {"Authorization": api_key}
    urls = []
    for kw in (keywords or ["abstract background"]):
        try:
            r = requests.get(
                PEXELS_SEARCH, headers=headers,
                params={"query": kw, "orientation": "portrait", "per_page": per_query},
                timeout=30,
            )
            r.raise_for_status()
            for video in r.json().get("videos", []):
                files = sorted(video.get("video_files", []),
                               key=lambda f: (f.get("height") or 0), reverse=True)
                for f in files:
                    if f.get("link"):
                        urls.append(f["link"])
                        break
        except Exception as e:
            print(f"  pexels '{kw}' skip: {e}")
    return urls


def search_pixabay(keywords, api_key=None, per_query=2):
    """Pixabay se video clips ke URLs (CC0, free, no attribution)."""
    api_key = api_key or os.environ.get("PIXABAY_API_KEY")
    if not api_key:
        return []
    urls = []
    for kw in (keywords or ["abstract background"]):
        try:
            r = requests.get(
                PIXABAY_SEARCH,
                params={"key": api_key, "q": kw, "per_page": max(3, per_query)},
                timeout=30,
            )
            r.raise_for_status()
            for hit in r.json().get("hits", [])[:per_query]:
                v = hit.get("videos", {})
                pick = v.get("large") or v.get("medium") or v.get("small")
                if pick and pick.get("url"):
                    urls.append(pick["url"])
        except Exception as e:
            print(f"  pixabay '{kw}' skip: {e}")
    return urls


def gather_clip_urls(keywords, pexels_key=None):
    """Pexels + Pixabay dono se clips jama, dedup + shuffle (zyada variety)."""
    import random
    urls = search_pexels(keywords, pexels_key) + search_pixabay(keywords)
    random.shuffle(urls)
    seen, out = set(), []
    for u in urls:
        if u and u not in seen:
            seen.add(u)
            out.append(u)
    return out


def _download(url, path):
    r = requests.get(url, stream=True, timeout=60)
    r.raise_for_status()
    with open(path, "wb") as f:
        for chunk in r.iter_content(8192):
            f.write(chunk)
    return path


def _normalize_clip(src, dst, clip_seconds):
    """Clip ko 1080x1920 me crop/scale + fixed length pe trim, audio hata do."""
    _run([
        "ffmpeg", "-y", "-i", src,
        "-t", f"{clip_seconds:.2f}",
        "-vf", f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1",
        "-an", "-r", "30",
        "-c:v", "libx264", "-preset", PRESET, "-pix_fmt", "yuv420p", dst,
    ])


def _make_captions_srt(audio_path, srt_path, words_per_chunk=3):
    """faster-whisper se word timestamps -> chhote chunks wali SRT file."""
    segments, _ = _whisper().transcribe(audio_path, word_timestamps=True)
    words = []
    for seg in segments:
        for w in (seg.words or []):
            words.append((w.start, w.end, w.word.strip()))

    def ts(t):
        h = int(t // 3600); m = int((t % 3600) // 60)
        s = int(t % 60); ms = int((t - int(t)) * 1000)
        return f"{h:02}:{m:02}:{s:02},{ms:03}"

    lines, idx = [], 1
    for i in range(0, len(words), words_per_chunk):
        chunk = words[i:i + words_per_chunk]
        start, end = chunk[0][0], chunk[-1][1]
        text = " ".join(c[2] for c in chunk).upper()
        lines.append(f"{idx}\n{ts(start)} --> {ts(end)}\n{text}\n")
        idx += 1
    with open(srt_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return srt_path


def render_faceless_segment(
    segment,
    audio_path,
    output_path,
    pexels_api_key=None,
    workdir="_work_faceless",
    add_captions=True,
):
    """
    Ek faceless segment ki clip banata hai.
    segment: {"keywords": [...], "text": "...", ...}
    audio_path: is segment ka voiceover mp3
    return: output_path
    """
    os.makedirs(workdir, exist_ok=True)
    audio_dur = _media_duration(audio_path)

    # 1) clips dono sources se (Pexels + Pixabay)
    urls = gather_clip_urls(segment.get("keywords"), pexels_api_key)
    if not urls:
        urls = gather_clip_urls(["cinematic background"], pexels_api_key)
    if not urls:
        raise RuntimeError("Pexels/Pixabay se koi clip nahi mili.")

    # 2) har clip ko barabar time do, normalize karo
    per_clip = max(2.0, audio_dur / len(urls))
    norm_clips = []
    for i, url in enumerate(urls):
        raw = os.path.join(workdir, f"raw_{i}.mp4")
        norm = os.path.join(workdir, f"norm_{i}.mp4")
        try:
            _download(url, raw)
            _normalize_clip(raw, norm, per_clip)
            norm_clips.append(norm)
        except Exception as e:
            print(f"  clip {i} skip: {e}")
    if not norm_clips:
        raise RuntimeError("Koi clip normalize nahi hui.")

    # 3) clip sequence (audio cover karne ke liye loop; crossfade ka time bhi count)
    step = per_clip - TRANSITION if EFFECTS else per_clip
    n_needed = max(1, int((audio_dur + per_clip) / max(0.5, step)) + 1)
    seq = [norm_clips[k % len(norm_clips)] for k in range(n_needed)]

    # 4) captions filter (dono modes me lagta hai)
    srt = None
    if add_captions:
        srt = os.path.join(workdir, "captions.srt")
        _make_captions_srt(audio_path, srt)
    style = ("FontName=Arial,FontSize=16,Bold=1,PrimaryColour=&H00FFFFFF,"
             "OutlineColour=&H00000000,Outline=3,Alignment=2,MarginV=240")

    fade_out_st = max(0.0, audio_dur - 0.5)

    if EFFECTS and len(seq) > 1:
        # ---- EFFECTS: crossfade transitions + fade in/out ----
        cmd = ["ffmpeg", "-y"]
        for c in seq:
            cmd += ["-i", c]
        cmd += ["-i", audio_path]   # last input = audio

        # xfade chain: offset_k = k*(per_clip - TRANSITION)
        parts, label = [], "0"
        for k in range(1, len(seq)):
            off = k * (per_clip - TRANSITION)
            if k < len(seq) - 1:
                out = f"x{k}"
                parts.append(f"[{label}][{k}]xfade=transition=fade:"
                             f"duration={TRANSITION}:offset={off:.2f}[{out}]")
                label = out
            else:
                tail = (f"[{label}][{k}]xfade=transition=fade:duration={TRANSITION}:"
                        f"offset={off:.2f},fade=t=in:st=0:d=0.4,"
                        f"fade=t=out:st={fade_out_st:.2f}:d=0.5")
                if srt:
                    tail += f",subtitles={srt}:force_style='{style}'"
                tail += "[v]"
                parts.append(tail)
        filter_complex = ";".join(parts)
        audio_idx = len(seq)
        cmd += ["-filter_complex", filter_complex,
                "-map", "[v]", "-map", f"{audio_idx}:a:0",
                "-c:v", "libx264", "-preset", PRESET, "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-shortest", output_path]
        _run(cmd)
        return output_path

    # ---- fallback: hard-cut concat (EFFECTS off ya 1 hi clip) ----
    concat_file = os.path.join(workdir, "concat.txt")
    with open(concat_file, "w") as f:
        for c in seq:
            f.write(f"file '{os.path.abspath(c)}'\n")
    silent = os.path.join(workdir, "silent.mp4")
    _run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_file,
          "-c", "copy", silent])

    sub_filter = []
    if srt:
        sub_filter = ["-vf", f"subtitles={srt}:force_style='{style}'"]
    _run([
        "ffmpeg", "-y", "-i", silent, "-i", audio_path,
        *sub_filter,
        "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "libx264", "-preset", PRESET, "-pix_fmt", "yuv420p", "-c:a", "aac",
        "-shortest", output_path,
    ])
    return output_path


if __name__ == "__main__":
    seg = {"text": "Get sunlight within ten minutes of waking up.",
           "keywords": ["sunrise", "morning window", "nature"]}
    # pehle is text ka voiceover bana lein (make_voice.py se), phir:
    # from make_voice import make_voiceover
    # make_voiceover(seg["text"], "seg_audio.mp3")
    render_faceless_segment(seg, "seg_audio.mp3", "faceless_segment.mp4")
    print("Done -> faceless_segment.mp4")
          
