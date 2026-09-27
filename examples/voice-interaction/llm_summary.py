"""Opt-in LLM summarizer for the Stop hook.

Enable with ZRB_VOICE_SUMMARY=llm.

Why this is NOT the default
---------------------------
It costs one extra model call per turn and adds seconds of latency *after the
answer is already on screen*. On a long response the deterministic cleaner
(voice_speaker.clean_for_speech) is faster, free, and good enough for most
turns. Reach for this only when the cleaned text reads badly aloud.

The call is synchronous by design. An async/fire-and-forget summary has no
ordering guarantee with the next turn, so you can hear turn N's summary after
turn N+1's answer has already appeared.
"""

from __future__ import annotations

import os

PROMPT = (
    "Rewrite the following assistant response as something that sounds natural "
    "when read aloud by a text-to-speech engine. Keep only what a listener "
    "needs: the conclusion and any action they must take. Drop code, file "
    "paths, tables, and tool mechanics. At most 2 sentences, at most 60 words. "
    "Reply with the spoken text only, no preamble."
)


def summarize_with_llm(text: str) -> str:
    """Return a spoken-form summary of *text*, or '' to fall back to cleanup."""
    import litellm

    model = os.getenv("ZRB_VOICE_SUMMARY_MODEL") or os.getenv("ZRB_LLM_MODEL")
    if not model:
        raise RuntimeError("no model configured (ZRB_VOICE_SUMMARY_MODEL/ZRB_LLM_MODEL)")

    response = litellm.completion(
        model=model,
        messages=[
            {"role": "system", "content": PROMPT},
            {"role": "user", "content": text[:8000]},
        ],
        temperature=0.0,
        timeout=float(os.getenv("ZRB_VOICE_SUMMARY_TIMEOUT", "20")),
    )
    content = response.choices[0].message.content or ""
    return content.strip()
