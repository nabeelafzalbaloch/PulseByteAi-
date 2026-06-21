"""
generate_script.py  (UPGRADED — YouTube Strategist format)
----------------------------------------------------------
Ahmad bhai ke strategist spec ke mutabiq: strong hook, bullet-style engaging
facts, SEO title (<=60 chars), 200-word description, 5 keywords, 3 hashtags,
fast-paced multi-platform tone, aur end pe CTA.

Output (pipeline-compatible + naye fields):
    {
      "title": str,            # SEO, <=60 chars
      "hook": str,             # 0-3s scroll-stopper
      "hook_type": str,
      "hook_options": [...],
      "script": str,           # full voiceover: hook + bullet facts + CTA
      "scenes": [{"text","visual","keywords"}],
      "description": str,      # ~200 word summary
      "keywords": [str x5],    # high-ranking
      "hashtags": [str x3],
      "video_flow_notes": str  # pacing/transition guidance
    }
"""

import os
import json
import time
import anthropic

MODEL = "claude-sonnet-4-6"

HOOK_FRAMEWORKS = """HOOK FRAMEWORKS (pick the strongest per topic):
1. Curiosity gap   2. Contrarian/negative ("Stop doing X")   3. Bold promise
4. Pointed question   5. Mistake/warning   6. Specific number
7. Relatable callout   8. Surprising fact
RULES: first 3 words decide the scroll; prefer a PATTERN INTERRUPT (visual + vocal
shock); no generic openers; hook must match the payoff."""

SYSTEM_PROMPT = """You are an expert content strategist for PulseByte, a YouTube channel
focused on AI-driven historical and technological storytelling. Your goal is highly
accurate, engaging, culturally authentic short-form scripts.

=== CRITICAL GEOGRAPHICAL ACCURACY (non-negotiable) ===
- When you mention a city in Pakistan, use ONLY landmarks, culture, and history that
  are specific to THAT city.
- NEVER default to generic national landmarks (Badshahi Mosque, Minar-e-Pakistan,
  Faisal Mosque) unless the subject city is literally that place (Lahore / Islamabad).
- If a video is about a specific city (e.g. Kasur, Multan, Faisalabad), research and
  mention only that location's own landmarks, figures, and stories.
- If you are NOT sure a monument/figure truly belongs to that city, SKIP it. It is
  always better to omit a landmark than to state incorrect geography.
- Verify location accuracy internally BEFORE drafting. On any conflict, drop the
  popular-but-wrong landmark and keep only authentic local details.

=== STYLE & TONE ===
- Strong, curiosity-driven hook.
- Punchy, rhythmic language, ideal for ElevenLabs AI narration (easy to speak aloud).
- Avoid clichés and repetitive phrasing.
- Always tie the history to the "soul" / identity of the place.

You write fast-paced scripts for YouTube Shorts, TikTok, Instagram Reels and Facebook
Reels. Success is measured by retention and shares.

""" + HOOK_FRAMEWORKS + """

WRITE THE SCRIPT THIS WAY:
- HOOK (0-3s): one strong, visually appealing, curiosity-sparking line.
- BODY: 3-5 short segments, each a punchy bullet-style engaging FACT. Keep technical
  terms simple. Each segment ends on a micro-cliffhanger to pull the viewer forward.
- CTA (end): invite viewers to subscribe and to comment their opinion.

ALSO PRODUCE:
- TITLE: clickable + SEO-friendly, MAX 60 characters.
- DESCRIPTION: ~200 words summarizing the video for YouTube.
- KEYWORDS: 5 high-ranking search keywords.
- HASHTAGS: exactly 3 relevant hashtags.
- VIDEO_FLOW_NOTES: short notes on pacing, suggested visuals, and where transitions/
  zoom effects should hit.

Respond with ONLY a valid JSON object, no markdown:
{
  "title": "... (<=60 chars)",
  "hook_options": [{"hook":"...","framework":"...","score":9,"why":"..."}],
  "hook": "best hook",
  "hook_type": "framework of chosen hook",
  "script": "full spoken voiceover: hook, then bullet-style facts, then CTA",
  "scenes": [{"text":"spoken line (ends on micro-cliffhanger)","visual":"what to show","keywords":["stock","terms"]}],
  "description": "~200 word YouTube description",
  "keywords": ["k1","k2","k3","k4","k5"],
  "hashtags": ["#a","#b","#c"],
  "video_flow_notes": "pacing + transition/effect guidance"
}"""


def _extract_json(text):
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text.strip())


def _build_prompt(topic, video_type, duration, language, brand_voice):
    parts = [
        f"Topic: {topic}",
        f"Video type: {video_type}",
        f"Target duration: {duration} seconds (~2.2 words/second)",
        f"Language: {language}",
    ]
    if brand_voice:
        parts.append(f"Brand voice: {brand_voice}")
    parts.append("Generate the full strategist JSON now.")
    return "\n".join(parts)


def generate_script(topic, video_type="faceless", duration=30, language="English",
                    brand_voice=None, api_key=None, max_retries=3):
    brand_voice = brand_voice if brand_voice is not None else os.environ.get("BRAND_VOICE", "")
    client = anthropic.Anthropic(api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"))
    prompt = _build_prompt(topic, video_type, duration, language, brand_voice)

    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            resp = client.messages.create(
                model=MODEL, max_tokens=2500, system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            )
            data = _extract_json(resp.content[0].text)

            best = max(data["hook_options"], key=lambda h: h.get("score", 0)) \
                if data.get("hook_options") else None
            if not data.get("hook") and best:
                data["hook"] = best["hook"]
            if not data.get("hook_type") and best:
                data["hook_type"] = best.get("framework", "")

            for field in ("title", "hook", "script", "hashtags"):
                if not data.get(field):
                    raise ValueError(f"Missing/empty field: {field}")

            # Title <=60 chars enforce
            if len(data["title"]) > 60:
                data["title"] = data["title"][:57].rstrip() + "..."

            data.setdefault("hook_options", [])
            data.setdefault("hook_type", "")
            data.setdefault("scenes", [])
            data.setdefault("description", "")
            data.setdefault("keywords", [])
            data.setdefault("video_flow_notes", "")
            data["hashtags"] = data["hashtags"][:3]   # spec: 3 hashtags
            data["keywords"] = data["keywords"][:5]    # spec: 5 keywords
            return data

        except (json.JSONDecodeError, ValueError) as e:
            last_error = e
            time.sleep(1.5 * attempt)
        except anthropic.APIError as e:
            last_error = e
            time.sleep(2 * attempt)

    raise RuntimeError(f"Script generation failed: {last_error}")


if __name__ == "__main__":
    r = generate_script("hidden history of Kasur, Pakistan", duration=40)
    print("TITLE:", r["title"], f"({len(r['title'])} chars)")
    print("HOOK:", r["hook"])
    print("DESC:", r["description"][:120], "...")
    print("KEYWORDS:", r["keywords"])
    print("HASHTAGS:", r["hashtags"])
    print("FLOW:", r["video_flow_notes"][:120])
                          
