"""
make_voice.py  (chunking added for long scripts)
------------------------------------------------
Script text -> ElevenLabs voiceover (mp3).
Lambi script (5-min) ko sentence-chunks me TTS karke ffmpeg se jodta hai.

Return: {"audio_path": str, "duration": float|None}
Env: ELEVENLABS_API_KEY
"""

import os
import re
import time
import subprocess
from elevenlabs.client import ElevenLabs

DEFAULT_VOICE_ID = os.environ.get("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")
DEFAULT_MODEL = "eleven_multilingual_v2"
OUTPUT_FORMAT = "mp3_44100_128"
CHUNK_LIMIT = 3500   # chars per TTS request (safe)


def list_voices(api_key=None):
    client = ElevenLabs(api_key=api_key or os.environ.get("ELEVENLABS_API_KEY"))
    result = client.voices.search()
    for v in result.voices:
        print(f"{v.voice_id}  ->  {v.name}")
    return result.voices


def _get_duration(path):
    try:
        from mutagen.mp3 import MP3
        return round(MP3(path).info.length, 2)
    except Exception:
        return None


def _split_text(text, limit=CHUNK_LIMIT):
    """Sentence boundaries pe chunks (har chunk <= limit chars)."""
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    chunks, cur = [], ""
    for s in sentences:
        if len(cur) + len(s) + 1 <= limit:
            cur = (cur + " " + s).strip()
        else:
            if cur:
                chunks.append(cur)
            cur = s
    if cur:
        chunks.append(cur)
    return chunks or [text]


def _tts_one(client, text, out_path, voice_id, model_id, max_retries=3):
    last = None
    for attempt in range(1, max_retries + 1):
        try:
            stream = client.text_to_speech.convert(
                text=text, voice_id=voice_id, model_id=model_id,
                output_format=OUTPUT_FORMAT)
            with open(out_path, "wb") as f:
                for chunk in stream:
                    if chunk:
                        f.write(chunk)
            return out_path
        except Exception as e:
            last = e
            time.sleep(2 * attempt)
    raise RuntimeError(f"TTS failed: {last}")


def make_voiceover(text, output_path="voiceover.mp3", voice_id=DEFAULT_VOICE_ID,
                   model_id=DEFAULT_MODEL, api_key=None, max_retries=3):
    if not text or not text.strip():
        raise ValueError("Voiceover text khaali nahi ho sakta.")
    client = ElevenLabs(api_key=api_key or os.environ.get("ELEVENLABS_API_KEY"))

    # chhota text -> ek hi call
    if len(text) <= CHUNK_LIMIT:
        _tts_one(client, text, output_path, voice_id, model_id, max_retries)
        return {"audio_path": output_path, "duration": _get_duration(output_path)}

    # lamba text -> chunks -> jodo
    chunks = _split_text(text)
    parts = []
    base = os.path.splitext(output_path)[0]
    for i, ch in enumerate(chunks):
        p = f"{base}_part{i}.mp3"
        _tts_one(client, ch, p, voice_id, model_id, max_retries)
        parts.append(p)

    listfile = f"{base}_concat.txt"
    with open(listfile, "w") as f:
        for p in parts:
            f.write(f"file '{os.path.abspath(p)}'\n")
    subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", listfile,
                    "-c", "copy", output_path],
                   check=True, capture_output=True)
    for p in parts + [listfile]:
        try:
            os.remove(p)
        except OSError:
            pass
    return {"audio_path": output_path, "duration": _get_duration(output_path)}


if __name__ == "__main__":
    print(make_voiceover("Here are three morning habits that change your focus.",
                         "voiceover.mp3"))
    
