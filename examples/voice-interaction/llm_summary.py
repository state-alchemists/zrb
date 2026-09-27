"""Optional LLM rewrite of a response before it is spoken (ZRB_VOICE_SUMMARY=llm).

Off by default: it adds a model call and seconds of delay per turn. Uses any
OpenAI-compatible /chat/completions endpoint through urllib.
"""

from __future__ import annotations

import json
import os
import urllib.request

PROMPT = (
    "Rewrite the following assistant response as something that sounds natural "
    "when read aloud by a text-to-speech engine. Keep only what a listener "
    "needs: the conclusion and any action they must take. Drop code, file "
    "paths, tables, and tool mechanics. At most 2 sentences, at most 60 words. "
    "Reply with the spoken text only, no preamble."
)


def summarize_with_llm(text: str) -> str:
    """Return a spoken-form summary of *text*, or '' to fall back to cleanup."""
    key = os.getenv("ZRB_VOICE_SUMMARY_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("ZRB_VOICE_SUMMARY_API_KEY / OPENAI_API_KEY is not set")
    base_url = os.getenv("ZRB_VOICE_SUMMARY_BASE_URL", "https://api.openai.com/v1")
    body = {
        "model": os.getenv("ZRB_VOICE_SUMMARY_MODEL", "gpt-4o-mini"),
        "messages": [
            {"role": "system", "content": PROMPT},
            {"role": "user", "content": text[:8000]},
        ],
        "temperature": 0.0,
    }
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/chat/completions",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
    )
    timeout = float(os.getenv("ZRB_VOICE_SUMMARY_TIMEOUT", "20"))
    with urllib.request.urlopen(request, timeout=timeout) as response:
        reply = json.loads(response.read())
    return (reply["choices"][0]["message"]["content"] or "").strip()
