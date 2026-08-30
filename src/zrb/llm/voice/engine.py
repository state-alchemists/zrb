"""Voice engine: push-to-talk speech-to-text.

Opens the microphone, records audio until the caller signals stop, transcribes
the captured audio via a configurable backend, and returns the text.

All heavy imports are lazy — `sounddevice`, `vosk`, and `numpy` are only
imported when `start_listening()` is called.
"""

from __future__ import annotations

import asyncio
import io
import json
import logging
import os
import platform
import wave
from typing import TYPE_CHECKING

from zrb.config.config import CFG

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine

logger = logging.getLogger(__name__)


class VoiceEngine:
    """Push-to-talk speech-to-text engine.

    Usage:
        engine = VoiceEngine()
        stop_event = asyncio.Event()
        text = await engine.start_listening(stop_event)
        if text:
            buffer.insert_text(text)
    """

    def __init__(self) -> None:
        self._transcriber: Callable[[bytes], Coroutine[None, None, str]] | None = None

    @property
    def transcriber(self) -> "Callable[[bytes], Coroutine[None, None, str]] | None":
        """The cached transcriber backend, or None before one is resolved."""
        return self._transcriber

    @transcriber.setter
    def transcriber(
        self, value: "Callable[[bytes], Coroutine[None, None, str]] | None"
    ) -> None:
        self._transcriber = value

    @property
    def is_ready(self) -> bool:
        """True once a transcriber is resolved (no model download/init needed)."""
        return self._transcriber is not None

    def is_vosk_model_ready(self) -> bool:
        """True if the configured Vosk model is already downloaded/extracted."""
        return get_vosk_model_dir(CFG.LLM_VOICE_VOSK_MODEL_NAME) is not None

    async def download_vosk_model(self) -> str:
        """Download+extract the configured Vosk model; return its directory."""
        return await download_vosk_model(
            CFG.LLM_VOICE_VOSK_MODEL_NAME, CFG.LLM_VOICE_VOSK_MODEL_URL
        )

    async def start_listening(self, stop_event: asyncio.Event) -> str:
        """Open the microphone, record until *stop_event* is set, transcribe.

        Returns the transcribed text, or an empty string if nothing was spoken.
        Raises on hardware/import/transcription errors so the UI can surface them.
        """
        audio_bytes = await self.record(stop_event)
        if not audio_bytes:
            return ""
        return await self.transcribe(audio_bytes)

    async def record(self, stop_event: asyncio.Event) -> bytes:
        """Record audio from the microphone until *stop_event* is set.

        Returns raw PCM int16 audio bytes, or empty bytes if cancelled.
        Raises RuntimeError if the microphone cannot be opened.
        """
        # lazy: heavy third-party
        import numpy as np
        import sounddevice as sd

        sample_rate = 16000
        channels = 1

        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[np.ndarray] = asyncio.Queue()

        def callback(indata, frames, time_info, status):
            if status:
                logger.debug("sounddevice status: %s", status)
            loop.call_soon_threadsafe(queue.put_nowait, indata.copy())

        try:
            stream = sd.InputStream(
                samplerate=sample_rate,
                channels=channels,
                dtype="float32",
                callback=callback,
            )
        except Exception as e:
            raise RuntimeError(
                f"Cannot open microphone: {e}. Check permissions and "
                f"that no other app is using the mic."
            ) from e

        buffer: list[np.ndarray] = []
        with stream:
            while True:
                if stop_event.is_set():
                    break
                try:
                    block = await asyncio.wait_for(queue.get(), timeout=0.1)
                    buffer.append(block)
                except asyncio.TimeoutError:
                    continue

        if not buffer:
            return b""

        audio_data = np.concatenate(buffer, axis=0)
        audio_int16 = (audio_data * 32767).astype(np.int16)
        return audio_int16.tobytes()

    async def transcribe(self, audio_bytes: bytes) -> str:
        """Transcribe audio bytes to text using the configured backend.

        Raises RuntimeError if no backend is available or transcription fails.
        """
        transcriber = await self.get_transcriber()
        return await transcriber(audio_bytes)

    async def get_transcriber(
        self,
    ) -> Callable[[bytes], Coroutine[None, None, str]]:
        """Resolve the transcription backend based on CFG.LLM_VOICE_MODE.

        Raises RuntimeError if the backend is unknown or dependencies are missing.
        """
        if self._transcriber is not None:
            return self._transcriber

        mode = CFG.LLM_VOICE_MODE.strip().lower()

        try:
            if mode == "vosk":
                self._transcriber = await self.make_vosk_transcriber()
            elif mode == "openai":
                self._transcriber = self.make_openai_transcriber()
            elif mode == "google":
                self._transcriber = self.make_google_transcriber()
            elif mode == "multimodal":
                self._transcriber = await self.make_multimodal_transcriber()
            else:
                raise RuntimeError(
                    f"Unknown voice mode: {mode!r}. "
                    f"Set {CFG.ENV_PREFIX}_LLM_VOICE_MODE to one of: vosk, openai, google, multimodal."
                )
        except ImportError as e:
            raise RuntimeError(
                f"Voice backend '{mode}' requires missing dependencies: {e}."
            ) from e

        return self._transcriber

    async def make_vosk_transcriber(
        self,
    ) -> Callable[[bytes], Coroutine[None, None, str]]:
        """Create a Vosk (offline) transcriber."""
        try:
            # lazy: heavy third-party
            from vosk import KaldiRecognizer, Model
        except ImportError:
            system = platform.system()
            if system == "Darwin":
                raise ImportError(
                    "vosk is not installed or not compatible with this macOS version.\n"
                    "  pip install vosk==0.3.44\n"
                    "Or use a different voice backend:\n"
                    f"  {CFG.ENV_PREFIX}_LLM_VOICE_MODE=openai|google"
                ) from None
            raise ImportError(
                "vosk is not installed.\n"
                "  pip install vosk sounddevice numpy\n"
                f"Or switch backends: {CFG.ENV_PREFIX}_LLM_VOICE_MODE=openai|google"
            ) from None

        model_name = CFG.LLM_VOICE_VOSK_MODEL_NAME
        model_url = CFG.LLM_VOICE_VOSK_MODEL_URL
        model_dir = get_vosk_model_dir(model_name)
        model_path: str | None = None

        if model_dir and os.path.isdir(model_dir):
            model_path = model_dir
        else:
            model_path = await download_vosk_model(model_name, model_url)

        try:
            model = await asyncio.to_thread(Model, model_path)
        except Exception as e:
            raise RuntimeError(
                f"Vosk model not found at {model_path}: {e}\n"
                f"Manually download from {model_url} or configure\n"
                f"{CFG.ENV_PREFIX}_LLM_VOICE_VOSK_MODEL_NAME / {CFG.ENV_PREFIX}_LLM_VOICE_VOSK_MODEL_URL."
            ) from e
        sample_rate = 16000

        async def transcribe(audio_bytes: bytes) -> str:
            rec = KaldiRecognizer(model, sample_rate)
            if rec.AcceptWaveform(audio_bytes):
                result = json.loads(rec.Result())
            else:
                result = json.loads(rec.FinalResult())
            return result.get("text", "")

        return transcribe

    def make_openai_transcriber(
        self,
    ) -> Callable[[bytes], Coroutine[None, None, str]]:
        """Create an OpenAI Whisper API transcriber."""
        try:
            # lazy: heavy third-party
            from openai import AsyncOpenAI
        except ImportError:
            raise ImportError("openai is not installed. pip install openai.") from None

        api_key = os.getenv("OPENAI_API_KEY", "")
        if not api_key:
            raise RuntimeError(
                "OPENAI_API_KEY is not set. Set it, or switch backends: "
                f"{CFG.ENV_PREFIX}_LLM_VOICE_MODE=vosk|google|multimodal."
            )
        client = AsyncOpenAI(api_key=api_key)
        model_name = CFG.LLM_VOICE_OPENAI_MODEL

        async def transcribe(audio_bytes: bytes) -> str:
            wav_buffer = io.BytesIO(pcm16_to_wav_bytes(audio_bytes))
            wav_buffer.name = "audio.wav"
            result = await client.audio.transcriptions.create(
                model=model_name,
                file=wav_buffer,
            )
            return result.text

        return transcribe

    def make_google_transcriber(
        self,
    ) -> Callable[[bytes], Coroutine[None, None, str]]:
        """Create a Google STT API transcriber."""
        try:
            # lazy: heavy third-party
            from google import genai
        except ImportError:
            raise ImportError(
                "google-genai is not installed. pip install google-genai."
            ) from None

        api_key = os.getenv("GEMINI_API_KEY", os.getenv("GOOGLE_API_KEY", ""))
        if not api_key:
            raise RuntimeError(
                "GEMINI_API_KEY (or GOOGLE_API_KEY) is not set. Set one, or switch "
                f"backends: {CFG.ENV_PREFIX}_LLM_VOICE_MODE=vosk|openai|multimodal."
            )
        client = genai.Client(api_key=api_key)
        model_name = CFG.LLM_VOICE_GOOGLE_MODEL

        async def transcribe(audio_bytes: bytes) -> str:
            # lazy: heavy third-party
            from google.genai import types

            wav_bytes = pcm16_to_wav_bytes(audio_bytes)

            response = await asyncio.to_thread(
                client.models.generate_content,
                model=model_name,
                contents=[
                    types.Part.from_bytes(data=wav_bytes, mime_type="audio/wav"),
                    "Transcribe this audio to text. Return only the transcription.",
                ],
            )
            return response.text.strip() if response.text else ""

        return transcribe

    async def make_multimodal_transcriber(
        self,
    ) -> Callable[[bytes], Coroutine[None, None, str]]:
        """Create a transcriber using the configured multimodal LLM.

        Uses `CFG.LLM_MULTIMODAL_MODEL` to transcribe audio. This backend works
        with providers whose pydantic-ai implementation accepts audio as a
        content block (e.g. Google Gemini). OpenAI models are explicitly rejected
        because the chat completions API does not accept audio content blocks —
        users should set ``ZRB_LLM_VOICE_MODE=openai`` for Whisper API instead.
        """
        # lazy: zrb internal (heavy via transitive) — not a cycle, verified
        # empirically (nothing zrb.llm.agent's package __init__ imports at
        # module level reaches zrb.llm.voice).
        from zrb.llm.agent import create_agent, run_agent
        from zrb.llm.config.config import llm_config
        from zrb.llm.config.limiter import llm_limiter
        from zrb.llm.prompt.prompt import get_prompt
        from zrb.llm.util.capabilities import model_capabilities

        multimodal_model = llm_config.multimodal_model
        if multimodal_model is None:
            raise RuntimeError(
                "LLM_MULTIMODAL_MODEL is not configured. "
                f"Set {CFG.ENV_PREFIX}_LLM_MULTIMODAL_MODEL or switch to a different voice backend."
            )

        resolved = llm_config.resolve_model(multimodal_model)
        if is_openai_chat_model(resolved):
            name = model_name(multimodal_model)
            raise RuntimeError(
                f"Multimodal model {name!r} is from OpenAI, which does not "
                f"accept audio content blocks in the chat completions API "
                f"(pydantic-ai limitation). "
                f"Set {CFG.ENV_PREFIX}_LLM_VOICE_MODE=openai to use the Whisper API, "
                f"or set {CFG.ENV_PREFIX}_LLM_MULTIMODAL_MODEL to a model that supports "
                f"inline audio (e.g. gemini-2.5-flash)."
            )

        if not model_capabilities.supports_modality(multimodal_model, "audio"):
            name = model_name(multimodal_model)
            raise RuntimeError(
                f"Multimodal model {name!r} does not support audio "
                f"transcription. Set {CFG.ENV_PREFIX}_LLM_VOICE_MODE to one of: "
                f"vosk, openai, google, or choose a model that "
                f"supports audio input."
            )

        system_prompt = get_prompt("multimodal_audio")

        async def transcribe(audio_bytes: bytes) -> str:
            # lazy: zrb internal (heavy via transitive)
            from zrb.llm.agent.types import BinaryContent

            agent = create_agent(
                model=resolved,
                system_prompt=system_prompt,
                yolo=True,
                resolve_model=False,
            )
            result, _ = await run_agent(
                agent=agent,
                message="Transcribe this audio to text. Return only the transcription.",
                message_history=[],
                limiter=llm_limiter,
                attachments=[BinaryContent(data=audio_bytes, media_type="audio/wav")],
            )
            return str(result).strip()

        return transcribe


# --- helpers below callers (per AGENTS.md convention) ------------------------


def vosk_installed() -> bool:
    """True when the vosk package is available for import."""
    # lazy: heavy third-party — find_spec avoids importing the package.
    import importlib.util

    try:
        return importlib.util.find_spec("vosk") is not None
    except ValueError:
        return False


def is_openai_chat_model(model: object) -> bool:
    """True for OpenAI chat models that cannot receive audio as content blocks.

    Checks both pydantic-ai :class:`~pydantic_ai.models.openai.OpenAIChatModel`
    instances and string model identifiers (``openai:gpt-4o``, ``gpt-4o``, etc.)
    """
    # lazy: heavy third-party
    try:
        from pydantic_ai.models.openai import OpenAIChatModel

        if isinstance(model, OpenAIChatModel):
            return True
    except ImportError:
        pass
    if isinstance(model, str):
        name = model.strip().lower()
        if name.startswith("openai:"):
            return True
        if name.startswith(("gpt-", "o1", "o3", "o4")):
            return True
    return False


def model_name(model: str | object) -> str:
    """Extract a user-friendly identifier from a model string or object."""
    if isinstance(model, str):
        return model
    for attr in ("model_name", "name"):
        value = getattr(model, attr, None)
        if isinstance(value, str) and value:
            return value
    return str(type(model).__name__)


def pcm16_to_wav_bytes(audio_bytes: bytes) -> bytes:
    """Wrap raw mono 16-bit 16kHz PCM audio in a WAV container."""
    wav_buffer = io.BytesIO()
    with wave.open(wav_buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(audio_bytes)
    return wav_buffer.getvalue()


def get_vosk_model_dir(model_name: str) -> str | None:
    """Return path to an existing Vosk model, or None."""
    cache = os.path.join(os.path.expanduser("~"), ".cache", "vosk")
    model_path = os.path.join(cache, model_name)
    if os.path.isdir(model_path):
        return model_path
    env_path = os.getenv("VOSK_MODEL_PATH")
    if env_path and os.path.isdir(env_path):
        return env_path
    return None


async def download_vosk_model(
    model_name: str, model_url: str
) -> (
    str
):  # noqa: C901 -- registration/factory fn; mccabe sums nested handlers into this line, radon scores each separately (near-trivial on its own)
    """Download and extract a Vosk model.

    The response body is read in 64 KiB chunks with an ``await`` between each,
    so the coroutine is cancellable (``/q`` or Ctrl+C) at chunk boundaries
    instead of blocking on one uninterruptible read. On cancellation the socket
    is closed in ``finally``, releasing the in-flight worker thread.

    Returns the model path on success.
    Raises RuntimeError if the download or extraction fails.
    """
    # lazy: heavy (stdlib) — urllib.request drags in ssl/http and zipfile
    # drags in lzma/bz2, for a one-shot download path.
    import io as _io
    import urllib.request as _urllib
    import zipfile

    url = f"{model_url}/{model_name}.zip"
    cache = os.path.join(os.path.expanduser("~"), ".cache", "vosk")
    os.makedirs(cache, exist_ok=True)
    target_dir = os.path.join(cache, model_name)

    logger.info("Downloading Vosk model (%s) from %s", model_name, url)

    def _download_error(exc: Exception) -> RuntimeError:
        return RuntimeError(
            f"Failed to download Vosk model from {url}: {exc}\n"
            f"Manually download {model_name}.zip from {model_url}/\n"
            f"and extract to {cache}/"
        )

    try:
        resp = await asyncio.to_thread(_urllib.urlopen, url, timeout=120)
    except Exception as exc:
        raise _download_error(exc) from exc

    chunks: list[bytes] = []
    try:
        while True:
            # CancelledError (BaseException) skips `except Exception` below and
            # propagates, running `finally` to close the socket — the abort path.
            chunk = await asyncio.to_thread(resp.read, 1 << 16)
            if not chunk:
                break
            chunks.append(chunk)
    except Exception as exc:
        raise _download_error(exc) from exc
    finally:
        resp.close()
    zip_data = b"".join(chunks)

    def _do_extract() -> None:
        real_cache = os.path.realpath(cache)
        with zipfile.ZipFile(_io.BytesIO(zip_data)) as zf:
            for member in zf.namelist():
                member_path = os.path.realpath(os.path.join(cache, member))
                if member_path != real_cache and not member_path.startswith(
                    real_cache + os.sep
                ):
                    raise RuntimeError(
                        f"Refusing to extract Vosk model: unsafe path in "
                        f"archive member {member!r}"
                    )
            zf.extractall(cache)

    await asyncio.to_thread(_do_extract)

    if not os.path.isdir(target_dir):
        raise RuntimeError(
            f"Downloaded model zip did not produce expected directory {target_dir}.\n"
            f"Manually download {model_name}.zip from {model_url}/\n"
            f"and extract to {cache}/"
        )

    logger.info("Vosk model downloaded to %s", target_dir)
    return target_dir
