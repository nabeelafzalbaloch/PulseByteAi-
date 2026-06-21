"""
make_voice.py
-------------
Pipeline ka Stage 2: script text ko ElevenLabs se voiceover (mp3) me convert karta hai.

Stage 1 (generate_script.py) ke output ka "script" field yahan input jaata hai.
Output ek dict: {"audio_path": str, "duration": float}  -- duration se aage
video ki length set hogi.

Requirements:
    pip install elevenlabs mutagen
    export ELEVENLABS_API_KEY="..."   # ya niche api_key paas karein

Model selection:
    eleven_multilingual_v2  -> high quality (Urdu/Hindi/English narration) [default]
    eleven_v3               -> sabse expressive, 70+ languages
    eleven_flash_v2_5       -> low latency (real-time, halki quality)
"""

import os
import time
from elevenlabs.client import ElevenLabs

# Default voice. Apni pasand ki voice ka ID voices.search() se nikaalein (niche helper).
DEFAULT_VOICE_ID = "21m00Tcm4TlvDq8ikWAM"   # "Rachel" - default female voice
DEFAULT_MODEL = "eleven_multilingual_v2"
OUTPUT_FORMAT = "mp3_44100_128"


def list_voices(api_key=None):
    """Aap ke account ki available voices print karta hai (ID + name)."""
    client = ElevenLabs(api_key=api_key or os.environ.get("ELEVENLABS_API_KEY"))
    result = client.voices.search()
    for v in result.voices:
        print(f"{v.voice_id}  ->  {v.name}")
    return result.voices


def _get_duration(path):
    """mp3 ki length (seconds) nikaalta hai. mutagen na ho to None."""
    try:
        from mutagen.mp3 import MP3
        return round(MP3(path).info.length, 2)
    except Exception:
        return None


def make_voiceover(
    text,
    output_path="voiceover.mp3",
    voice_id=DEFAULT_VOICE_ID,
    model_id=DEFAULT_MODEL,
    api_key=None,
    max_retries=3,
):
    """
    Text ko speech me convert karke mp3 save karta hai.
    Return: {"audio_path": str, "duration": float | None}
    """
    if not text or not text.strip():
        raise ValueError("Voiceover ke liye text khaali nahi ho sakta.")

    client = ElevenLabs(api_key=api_key or os.environ.get("ELEVENLABS_API_KEY"))

    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            # convert() audio bytes ka stream/generator return karta hai
            audio_stream = client.text_to_speech.convert(
                text=text,
                voice_id=voice_id,
                model_id=model_id,
                output_format=OUTPUT_FORMAT,
            )
            with open(output_path, "wb") as f:
                for chunk in audio_stream:
                    if chunk:
                        f.write(chunk)

            duration = _get_duration(output_path)
            return {"audio_path": output_path, "duration": duration}

        except Exception as e:
            last_error = e
            time.sleep(2 * attempt)   # rate-limit / network backoff

    raise RuntimeError(f"Voiceover failed after {max_retries} tries: {last_error}")


if __name__ == "__main__":
    # Demo. Pehle apni voices dekhein:
    # list_voices()

    result = make_voiceover(
        text="Here are three morning habits that will completely change your focus.",
        output_path="voiceover.mp3",
        # voice_id="YOUR_VOICE_ID",   # apni voice yahan daalein
    )
    print(result)
