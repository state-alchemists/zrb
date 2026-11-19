"""Plain-`urllib` requests for the cloud backends: no package needed."""

from __future__ import annotations

import io
import json
import os
import urllib.request
import wave
from typing import BinaryIO


def post_json(url: str, body: dict, headers: dict, timeout: float | None) -> bytes:
    with open_post_json(url, body, headers, timeout) as response:
        return response.read()


def open_post_json(
    url: str, body: dict, headers: dict, timeout: float | None
) -> BinaryIO:
    """The response to a JSON POST, its body not read yet: it raises on an
    HTTP error here, and streams once read."""
    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", **headers},
    )
    return urllib.request.urlopen(request, timeout=timeout)


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
