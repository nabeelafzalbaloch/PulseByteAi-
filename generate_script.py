"""
generate_script.py  (PulseByteAi — web-researched + AI Uncovered style)
----------------------------------------------------------------------
Flow:
  1. web_research.research_topic(topic)  -> asli web facts (Tavily)
  2. Claude un facts + PulseByteAi ki winning style pe retention-first script likhta hai

Style "AI Uncovered": AI ka chhupa/khatarnaak sach; dark, urgent; pehle 3 second me
tension (swipe-away kam karne ke liye).

Output (pipeline-compatible):
  title(<=60), hook, hook_type, hook_options, script, scenes, description,
  keywords(5), hashtags(3), video_flow_notes

Env: ANTHROPIC_API_KEY  (zaroori) ; TAVILY_API_KEY (optional, web facts ke liye)
"""

import os
import json
import time
import anthropic
from web_research import research_topic

MODEL = "claude-sonnet-4-6"

HOOK_FRAMEWORKS = """HOOK FRAMEWORKS: 1.Curiosity gap 2.Contrarian("Stop...") 3.Bold promise
4.Pointed question 5.Mistake/warning 6.Specific number 7.Relatable callout 8.Surprising fact.
First 3 WORDS decide the scroll; prefer a PATTERN INTERRUPT (visual+vocal shock); no generic openers."""

SYSTEM_PROMPT = """You are the head scriptwriter for PulseByteAi, a fast-growing English
short-form channel (UK/USA audience) that EXPOSES the hidden, unsettling truths about AI.

=== CHANNEL VOICE: "AI UNCOVERED" ===
Tone: dark, urgent, "they don't want you to know this." Every video reveals a secret,
a threat, or something that feels forbidden about AI/technology. This is what already
works on the channel (top videos: a "ghost" in your phone, AI taking jobs, fake AI voices).

=== RETENTION RULES (the channel's #1 problem is people swiping away) ===
- The first 3 WORDS must create tension or name a threat. No slow intros, no "In this video".
- TEASE, don't explain. Make them stay to "find out."
- Every 5-7 seconds add a new turn/hook ("But here's the scary part...").
- End each fact UNFINISHED so the viewer can't swipe.
- Punchy, rhythmic, easy for an AI voice (ElevenLabs) to speak. Avoid cliches.

=== USE THE FACTS ===
If VERIFIED WEB FACTS are provided, build the script on them (accurate, specific, current).
Prefer them over assumptions. If a fact is unclear, leave it out rather than invent.

=== GEOGRAPHICAL ACCURACY (if a place is mentioned) ===
Use only landmarks/history specific to that exact place. Never default to generic national
landmarks. If unsure, skip it.

""" + HOOK_FRAMEWORKS + """

WRITE THE SCRIPT:
- HOOK (0-3s): pattern-interrupt naming the secret/threat.
- BODY: 3-5 punchy segments, each a bullet-style fact ending on a micro-cliffhanger.
- CTA (end): "Follow PulseByte..." + tease the next episode. Invite a comment.

ALSO PRODUCE: TITLE (clickable, <=60 chars), DESCRIPTION (~200 words),
KEYWORDS (5), HASHTAGS (exactly 3), VIDEO_FLOW_NOTES (pacing + where transitions hit).

Respond with ONLY valid JSON, no markdown:
{
  "title":"(<=60 chars)",
  "hook_options":[{"hook":"...","framework":"...","score":9,"why":"..."}],
  "hook":"best hook","hook_type":"framework",
  "script":"hook + bullet facts + CTA",
  "scenes":[{"text":"line (micro-cliffhanger)","visual":"what to show","keywords":["stock","terms"]}],
  "description":"~200 words","keywords":["k1","k2","k3","k4","k5"],
  "hashtags":["#a","#b","#c"],"video_flow_notes":"..."
}"""

LONG_SYSTEM_PROMPT = """You are the head scriptwriter for PulseByteAi, an English YouTube
channel (UK/USA) about AI and future technology. Write a LONG-FORM YouTube script
(several minutes) that is informative, engaging, and keeps viewers watching.

STRUCTURE (for a ~5 minute video, ~700-800 spoken words):
- HOOK (first 15s): a strong reason to keep watching.
- INTRO: what this video covers and why it matters to the viewer.
- 5 to 7 SECTIONS: each one clear point with detail, an example, and a smooth transition
  to the next. Keep language simple, confident, and natural for an AI voice (ElevenLabs).
- RECAP + CTA: quick summary, ask to subscribe and comment, tease the next video.

Accuracy: if VERIFIED WEB FACTS are given, build on them. Don't invent specifics.
Tone: knowledgeable but easy to follow. Avoid filler and repetition.

ALSO PRODUCE: TITLE (<=60 chars, SEO), DESCRIPTION (~200 words), KEYWORDS (5),
HASHTAGS (3), VIDEO_FLOW_NOTES, and SCENES (10-14 items) each with diverse visual
keywords so the video has variety.

Respond with ONLY valid JSON, no markdown:
{
  "title":"(<=60 chars)",
  "hook_options":[{"hook":"...","framework":"...","score":9,"why":"..."}],
  "hook":"best hook","hook_type":"framework",
  "script":"full long-form spoken voiceover: hook, intro, sections, recap, CTA",
  "scenes":[{"text":"section line","visual":"what to show","keywords":["stock","terms"]}],
  "description":"~200 words","keywords":["k1","k2","k3","k4","k5"],
  "hashtags":["#a","#b","#c"],"video_flow_notes":"..."
}"""


def _extract_json(text):
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text.strip())


def generate_script(topic, video_type="faceless", duration=30, language="English",
                    brand_voice=None, api_key=None, max_retries=3, use_research=True,
                    long_form=False):
    brand_voice = brand_voice if brand_voice is not None else os.environ.get("BRAND_VOICE", "")
    client = anthropic.Anthropic(api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"))

    facts = research_topic(topic) if use_research else ""
    system = LONG_SYSTEM_PROMPT if long_form else SYSTEM_PROMPT
    max_tokens = 4000 if long_form else 2500

    user = [
        f"Topic: {topic}",
        f"Duration: {duration} seconds (~2.2 words/sec)",
        f"Language: {language}",
    ]
    if brand_voice:
        user.append(f"Brand voice: {brand_voice}")
    if facts:
        user.append(f"\nVERIFIED WEB FACTS (use these):\n{facts}")
    else:
        user.append("\n(No web facts available — use your own knowledge, stay accurate.)")
    user.append("\nGenerate the full PulseByteAi JSON now.")
    prompt = "\n".join(user)

    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            resp = client.messages.create(
                model=MODEL, max_tokens=max_tokens, system=system,
                messages=[{"role": "user", "content": prompt}],
            )
            data = _extract_json(resp.content[0].text)

            best = max(data["hook_options"], key=lambda h: h.get("score", 0)) \
                if data.get("hook_options") else None
            if not data.get("hook") and best:
                data["hook"] = best["hook"]
            if not data.get("hook_type") and best:
                data["hook_type"] = best.get("framework", "")

            for f in ("title", "hook", "script", "hashtags"):
                if not data.get(f):
                    raise ValueError(f"Missing field: {f}")

            if len(data["title"]) > 60:
                data["title"] = data["title"][:57].rstrip() + "..."
            data.setdefault("hook_options", [])
            data.setdefault("hook_type", "")
            data.setdefault("scenes", [])
            data.setdefault("description", "")
            data.setdefault("keywords", [])
            data.setdefault("video_flow_notes", "")
            data["hashtags"] = data["hashtags"][:3]
            data["keywords"] = data["keywords"][:5]
            data["researched"] = bool(facts)
            return data

        except (json.JSONDecodeError, ValueError) as e:
            last_error = e
            time.sleep(1.5 * attempt)
        except anthropic.APIError as e:
            last_error = e
            time.sleep(2 * attempt)

    raise RuntimeError(f"Script generation failed: {last_error}")


if __name__ == "__main__":
    r = generate_script("AI that can clone your voice in 3 seconds", duration=40)
    print("RESEARCHED:", r.get("researched"))
    print("TITLE:", r["title"])
    print("HOOK:", r["hook"])
  
