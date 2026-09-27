"""Plain-`urllib` requests for the cloud backends: no package needed."""

from __future__ import annotations

import io
import json
import os
import urllib.request
import wave


def post_json(url: str, body: dict, headers: dict, timeout: float | None) -> bytes:
    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", **headers},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def pcm_to_wav(pcm: bytes, sample_rate: int = 24000) -> bytes:
    """Wrap mono 16-bit PCM in a WAV container."""
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(pcm)
    return buffer.getvalue()


def get_required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"{name} is not set")
    return value
