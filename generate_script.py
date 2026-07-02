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

Env: ANTHROPIC_API_KEY (primary) ; GEMINI_API_KEY (fallback, free) ; TAVILY_API_KEY (optional)
"""

import os
import json
import time
import requests
try:
    import anthropic
    _HAS_ANTHROPIC = True
except ImportError:
    _HAS_ANTHROPIC = False
from web_research import research_topic

MODEL = "claude-sonnet-4-6"
GEMINI_MODEL = "gemini-1.5-flash"
GEMINI_URL = ("https://generativelanguage.googleapis.com/v1beta/models/"
              + GEMINI_MODEL + ":generateContent")


def _call_gemini(system, prompt, api_key, max_tokens=2500):
    url = GEMINI_URL + "?key=" + api_key
    full_prompt = system + "\n\n" + prompt
    body = {
        "contents": [{"role": "user", "parts": [{"text": full_prompt}]}],
        "generationConfig": {"maxOutputTokens": max_tokens, "temperature": 0.9}
    }
    for attempt in range(3):
        r = requests.post(url, json=body, timeout=90)
        if r.status_code == 429:
            time.sleep(10 * (attempt + 1))
            continue
        r.raise_for_status()
        data = r.json()
        candidates = data.get("candidates", [])
        if not candidates:
            raise RuntimeError(f"Gemini empty response: {data}")
        return candidates[0]["content"]["parts"][0]["text"]
    raise RuntimeError("Gemini rate limit - 3 attempts failed")


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
- THE 3-SECOND HOOK: open with a PATTERN INTERRUPT — a shocking fact or counter-intuitive
  claim. The first 3 WORDS must create tension or name a threat. No "In this video", no slow intro.
- PACING: keep sentences UNDER 12 WORDS. Punchy, rhythmic, easy for an AI voice (ElevenLabs).
- CURIOSITY GAP: every ~20 seconds, hint at a "hidden truth" that you reveal slightly later.
  Reveal enough to intrigue, hide enough that they must keep watching.
- TEASE, don't explain. End each fact UNFINISHED so the viewer can't swipe.
- TONE: dark, urgent, conspiratorial, but data-backed (use the verified facts).

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

ALSO PRODUCE (SEO):
- TITLE_OPTIONS: exactly 3 titles — (1) clickbait/controversial, (2) search-optimized,
  (3) question-based. Then pick the strongest as "title" (<=60 chars).
- KEYWORDS: 5 total = 3 broad (e.g. AI, future tech) + 2 specific long-tail.
- HASHTAGS: exactly 3 relevant.
- DESCRIPTION (~200 words), VIDEO_FLOW_NOTES (pacing + where transitions hit).

Respond with ONLY valid JSON, no markdown:
{
  "title_options":["clickbait title","search title","question title"],
  "title":"(<=60 chars, the best one)",
  "hook_options":[{"hook":"...","framework":"...","score":9,"why":"..."}],
  "hook":"best hook","hook_type":"framework",
  "script":"hook + bullet facts + CTA",
  "scenes":[{"text":"line (micro-cliffhanger)","visual":"what to show","keywords":["stock","terms"]}],
  "description":"~200 words","keywords":["broad1","broad2","broad3","longtail1","longtail2"],
  "hashtags":["#a","#b","#c"],"video_flow_notes":"..."
}"""

LONG_SYSTEM_PROMPT = """You are the head scriptwriter for PulseByteAi, an English YouTube
channel (UK/USA) about AI and future technology. Write a LONG-FORM YouTube script
(several minutes) that is informative, engaging, and keeps viewers watching.

STRUCTURE (for a ~5 minute video, ~700-800 spoken words):
- 0:00-0:30 — THE HOOK: a pattern interrupt + why this matters RIGHT NOW.
- 0:30-4:00 — 5 DETAILED CHAPTERS: each chapter teaches one clear point with an example,
  and ENDS ON A PATTERN INTERRUPT or mini-cliffhanger that pulls the viewer into the next.
- 4:00-5:00 — RECAP + a CTA that forces a deep comment (ask a specific opinion question).
- Keep sentences punchy. Natural for an AI voice. Build on the verified facts.

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
                    long_form=False, feedback="", lessons=""):
    brand_voice = brand_voice if brand_voice is not None else os.environ.get("BRAND_VOICE", "")
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
    if lessons:
        user.append(f"\nCREATOR LESSONS from past performance — APPLY these:\n{lessons}")
    if feedback:
        user.append(f"\nIMPROVE ON THE LAST ATTEMPT. Reviewer feedback to fix:\n{feedback}")
    user.append("\nGenerate the full PulseByteAi JSON now.")
    prompt = "\n".join(user)

    # Claude pehle (best quality), Gemini fallback (free)
    anthropic_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
    gemini_key = os.environ.get("GEMINI_API_KEY", "")

    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            if anthropic_key and _HAS_ANTHROPIC:
                client = anthropic.Anthropic(api_key=anthropic_key)
                resp = client.messages.create(
                    model=MODEL, max_tokens=max_tokens, system=system,
                    messages=[{"role": "user", "content": prompt}],
                )
                data = _extract_json(resp.content[0].text)
            elif gemini_key:
                raw = _call_gemini(system, prompt, gemini_key, max_tokens)
                data = _extract_json(raw)
            else:
                raise RuntimeError("Koi API key nahi (ANTHROPIC_API_KEY ya GEMINI_API_KEY)")

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
        except Exception as e:
            last_error = e
            time.sleep(2 * attempt)

    raise RuntimeError(f"Script generation failed: {last_error}")


EVAL_SYSTEM = """You are a Master Content Strategist & Retention Specialist for short-form
AI-niche video (UK/USA). Rate the script 1-10 using these WEIGHTED criteria:
- Hook Strength (40%): is the first 3 seconds impossible to swipe away from?
- Curiosity Gap (30%): does it reveal enough to intrigue but hide enough to force watching?
- Pacing (20%): fast, rhythmic, punchy, sentences under 12 words?
- SEO Compatibility (10%): are keywords integrated naturally into title/description?
Be strict; most drafts are a 6 or 7. Compute the weighted score.
Return ONLY JSON, no markdown:
{"score": <number 1-10>, "strengths":"...", "weaknesses":"...", "fixes":"specific, actionable improvements"}"""


def evaluate_content(data, api_key=None):
    """Script plan ko rate karta hai. Return {score, strengths, weaknesses, fixes}."""
    anthropic_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
    gemini_key = os.environ.get("GEMINI_API_KEY", "")
    plan = (f"TITLE: {data.get('title','')}\n"
            f"HOOK: {data.get('hook','')}\n"
            f"SCRIPT: {data.get('script','')}\n"
            f"DESCRIPTION: {data.get('description','')}\n"
            f"KEYWORDS: {', '.join(data.get('keywords', []))}\n"
            f"HASHTAGS: {' '.join(data.get('hashtags', []))}")
    prompt = plan + "\n\nRate it now (JSON only)."
    try:
        if anthropic_key and _HAS_ANTHROPIC:
            client = anthropic.Anthropic(api_key=anthropic_key)
            resp = client.messages.create(
                model=MODEL, max_tokens=600, system=EVAL_SYSTEM,
                messages=[{"role": "user", "content": prompt}],
            )
            ev = _extract_json(resp.content[0].text)
        elif gemini_key:
            raw = _call_gemini(EVAL_SYSTEM, prompt, gemini_key, 600)
            ev = _extract_json(raw)
        else:
            return {"score": 7.0, "strengths": "", "weaknesses": "", "fixes": ""}
        ev["score"] = float(ev.get("score", 0))
        return ev
    except Exception as e:
        return {"score": 7.0, "strengths": "", "weaknesses": "",
                "fixes": "", "_eval_error": str(e)}


def generate_rated_script(topic, threshold=7.0, attempts=3, **kwargs):
    """generate -> self-rate -> agar score < threshold to feedback ke saath dobara."""
    api_key = kwargs.get("api_key")
    best, best_score, feedback = None, -1.0, ""
    for _ in range(max(1, attempts)):
        data = generate_script(topic, feedback=feedback, **kwargs)
        ev = evaluate_content(data, api_key=api_key)
        score = ev.get("score", 0)
        data["_score"] = score
        data["_eval"] = ev
        if score > best_score:
            best, best_score = data, score
        if score >= threshold:
            break
        feedback = (f"Score was {score}/10. Weaknesses: {ev.get('weaknesses','')}. "
                    f"Fixes: {ev.get('fixes','')}")
    return best, best_score


if __name__ == "__main__":
    data, score = generate_rated_script("AI that can clone your voice in 3 seconds")
    print("SCORE:", score)
    print("TITLE:", data["title"])
    print("HOOK:", data["hook"])
                      
