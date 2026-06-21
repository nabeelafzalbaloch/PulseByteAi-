"""
generate_script.py  (UPGRADED — hook-optimized)
-----------------------------------------------
Pipeline ka Stage 1: Claude API se viral-style script + metadata.

Naya kya hai:
  1. 8 proven HOOK FRAMEWORKS prompt me built-in (curiosity gap, contrarian,
     bold promise, etc.) -> generic ke bajaye scroll-stopping hooks.
  2. Claude pehle 5 HOOK OPTIONS banata hai, khud score/rank karta hai, aur
     sabse strong ko final hook bana kar uspe script likhta hai.
  3. BRAND VOICE + EXAMPLES slot -> aap ki niche ke jo hooks/videos chale hain
     unhe few-shot ke taur pe do, output aap ke style me dhal jaata hai.

Output (pipeline ke baaki stages ke saath compatible):
    {
      "title": str,
      "hook": str,                 # chosen best hook
      "hook_options": [ {"hook","framework","score","why"} , ... ],
      "script": str,
      "scenes": [ {"text","visual","keywords"} , ... ],
      "caption": str,
      "hashtags": [str, ...]
    }

Requirements:
    pip install anthropic
    export ANTHROPIC_API_KEY="sk-ant-..."
    # optional:
    export BRAND_VOICE="punchy, direct, no fluff, Gen-Z tone"
"""

import os
import json
import time
import anthropic

MODEL = "claude-sonnet-4-6"

# ---- Proven hook frameworks (yahi content quality ka asli engine hai) ----
HOOK_FRAMEWORKS = """HOOK FRAMEWORKS (use a different one per option, pick what fits best):
1. Curiosity gap     - tease the payoff without revealing it ("The reason you can't focus isn't what you think").
2. Contrarian/negative - challenge a common belief ("Stop drinking water first thing — do this instead").
3. Bold promise      - a clear, specific transformation ("Do this for 7 days and your mornings change").
4. Pointed question  - a question the viewer NEEDS answered ("Why do focused people never check their phone first?").
5. Mistake/warning   - call out a costly error ("You're ruining your mornings with this one habit").
6. Specific number   - concrete listicle ("3 ten-second habits that fixed my focus").
7. Relatable callout - name the exact viewer ("If you wake up tired no matter what — watch this").
8. Surprising fact   - a counterintuitive stat or truth ("90% of people use their most focused hour scrolling").

RULES:
- The FIRST 3 WORDS decide the scroll. Front-load tension or specificity.
- Prefer a PATTERN INTERRUPT opening (e.g. "Stop doing [X]...") with visual + vocal
  shock — something that breaks the viewer's autopilot.
- No generic openers ("In today's video", "Here are some tips").
- Hook must match the script's actual payoff (no clickbait that under-delivers).
- BODY RETENTION: each scene must end on a MICRO-CLIFFHANGER — a small open loop that
  makes the viewer need the next line ("...but the third one is what actually works")."""


SYSTEM_PROMPT = """You are an elite short-form video scriptwriter for YouTube Shorts,
Instagram Reels, TikTok and Facebook. You are known for hooks that stop the scroll
and scripts that hold retention to the last second.

""" + HOOK_FRAMEWORKS + """

PROCESS (do this internally, then output JSON):
- Write 5 distinct hook options, each using a DIFFERENT framework above.
- Score each 1-10 on scroll-stopping power and give a one-line reason.
- Pick the highest-scoring hook as the final hook.
- Write the full voiceover script that delivers on that hook, scene by scene, with
  each scene ending on a micro-cliffhanger.

Respond with ONLY a valid JSON object, no markdown, no preamble:
{
  "title": "...",
  "hook_options": [
    {"hook": "...", "framework": "curiosity gap", "score": 9, "why": "..."}
    // exactly 5
  ],
  "hook": "the single highest-scoring hook (copy it here)",
  "hook_type": "the framework name of the chosen hook",
  "script": "full spoken voiceover, starting with the chosen hook",
  "scenes": [
    {"text": "line spoken in this scene (ends on a micro-cliffhanger)",
     "visual": "what to show on screen",
     "keywords": ["stock", "search", "terms"]}
  ],
  "caption": "post caption with a soft call to action",
  "hashtags": ["#tag1", "#tag2"]
}"""


def _extract_json(text):
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text.strip())


def _build_prompt(topic, video_type, duration, language, brand_voice, examples):
    parts = [
        f"Topic: {topic}",
        f"Video type: {video_type}",
        f"Target duration: {duration} seconds (about 2.2 words/second of speech)",
        f"Language: {language}",
    ]
    if brand_voice:
        parts.append(f"\nBrand voice (write in this tone): {brand_voice}")
    if examples:
        ex = "\n".join(f"- {e}" for e in examples)
        parts.append(
            "\nThese hooks/videos performed well for this creator — match this "
            f"energy and style (do NOT copy them):\n{ex}")
    parts.append("\nGenerate the script JSON now.")
    return "\n".join(parts)


def generate_script(
    topic,
    video_type="faceless",
    duration=30,
    language="English",
    brand_voice=None,
    examples=None,
    api_key=None,
    max_retries=3,
):
    """Hook-optimized script generate karta hai. Dict return karta hai."""
    brand_voice = brand_voice if brand_voice is not None else os.environ.get("BRAND_VOICE", "")
    client = anthropic.Anthropic(api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"))
    prompt = _build_prompt(topic, video_type, duration, language, brand_voice, examples)

    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=2000,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            )
            data = _extract_json(response.content[0].text)

            # agar "hook" missing -> hook_options me se best pick karo
            best = None
            if data.get("hook_options"):
                best = max(data["hook_options"], key=lambda h: h.get("score", 0))
            if not data.get("hook") and best:
                data["hook"] = best["hook"]
            if not data.get("hook_type") and best:
                data["hook_type"] = best.get("framework", "")

            for field in ("title", "hook", "script", "hashtags"):
                if field not in data or not data[field]:
                    raise ValueError(f"Missing/empty field: {field}")
            data.setdefault("hook_options", [])
            data.setdefault("hook_type", "")
            data.setdefault("scenes", [])
            return data

        except (json.JSONDecodeError, ValueError) as e:
            last_error = e
            time.sleep(1.5 * attempt)
        except anthropic.APIError as e:
            last_error = e
            time.sleep(2 * attempt)

    raise RuntimeError(f"Script generation failed after {max_retries} tries: {last_error}")


if __name__ == "__main__":
    result = generate_script(
        topic="3 morning habits that boost focus",
        video_type="faceless",
        duration=30,
        brand_voice="punchy, direct, slightly bold, no fluff",
        examples=[
            "Nobody talks about how boring focus actually is.",
            "I tried waking at 5am for 30 days — here's the truth.",
        ],
    )
    print("CHOSEN HOOK:", result["hook"])
    print("\nALL OPTIONS:")
    for h in result["hook_options"]:
        print(f"  [{h.get('score')}] ({h.get('framework')}) {h.get('hook')}")
    print("\nSCRIPT:\n", result["script"])
          
