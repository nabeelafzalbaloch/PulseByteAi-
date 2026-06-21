"""
web_research.py
---------------
Topic ko web pe search karke asli, taaza facts laata hai (Tavily API).
Ye facts generate_script ko diye jaate hain taake script "best of the best" bane.

Tavily free tier: ~1000 searches/month, no card.
    export TAVILY_API_KEY="tvly-..."

Agar key na ho to khaali string deta hai (pipeline rukti nahi -> Claude apni
knowledge se likhta hai).
"""

import os
import requests

TAVILY_URL = "https://api.tavily.com/search"


def research_topic(topic, api_key=None, max_results=5):
    """Topic ke baare me web facts return karta hai (text block) ya "" agar na ho."""
    api_key = api_key or os.environ.get("TAVILY_API_KEY")
    if not api_key:
        return ""   # research optional -> graceful

    try:
        r = requests.post(
            TAVILY_URL,
            headers={"Authorization": f"Bearer {api_key}",
                     "Content-Type": "application/json"},
            json={
                "query": topic,
                "search_depth": "advanced",
                "max_results": max_results,
                "include_answer": "advanced",
            },
            timeout=40,
        )
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print(f"[web_research] failed: {e}")
        return ""

    parts = []
    if data.get("answer"):
        parts.append("SUMMARY: " + data["answer"].strip())
    for res in data.get("results", [])[:max_results]:
        content = (res.get("content") or "").strip()
        if content:
            parts.append(f"- {res.get('title', '')}: {content[:320]}")
    return "\n".join(parts)


if __name__ == "__main__":
    print(research_topic("latest AI that can clone a voice in seconds"))
