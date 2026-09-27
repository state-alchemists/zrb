"""Wrapping dictation audio for APIs that take a file."""

from __future__ import annotations

import io
import wave


def pcm16_to_wav_bytes(audio_bytes: bytes) -> bytes:
    """Wrap raw mono 16-bit 16kHz PCM audio in a WAV container."""
    wav_buffer = io.BytesIO()
    with wave.open(wav_buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(audio_bytes)
    return wav_buffer.getvalue()
