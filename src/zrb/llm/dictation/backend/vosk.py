"""Offline dictation with vosk; the model is downloaded on first use."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import platform
from collections.abc import Callable
from typing import Any

from zrb.config.config import CFG
from zrb.llm.dictation.backend.any_dictation_backend import AnyDictationBackend

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16000


class VoskDictationBackend(AnyDictationBackend):
    """vosk, offline; *model_name* is downloaded from *model_url* when missing."""

    def __init__(
        self,
        model_name: str = "vosk-model-small-en-us-0.15",
        model_url: str = "https://alphacephei.com/vosk/models",
    ) -> None:
        self._model_name = model_name
        self._model_url = model_url
        self._model: Any = None

    @property
    def name(self) -> str:
        return "vosk"

    @property
    def is_model_downloaded(self) -> bool:
        return get_vosk_model_dir(self._model_name) is not None

    async def prepare(self, report: Callable[[str], None]) -> None:
        if self._model is not None or self.is_model_downloaded:
            return
        report("Downloading the voice model...")
        await download_vosk_model(self._model_name, self._model_url)
        report("Voice model ready")

    async def transcribe(self, audio: bytes) -> str:
        model = await self._get_model()
        # lazy: heavy third-party; after the model, which reports it missing
        from vosk import KaldiRecognizer

        recognizer = KaldiRecognizer(model, SAMPLE_RATE)
        if recognizer.AcceptWaveform(audio):
            result = json.loads(recognizer.Result())
        else:
            result = json.loads(recognizer.FinalResult())
        return result.get("text", "")

    async def _get_model(self) -> Any:
        if self._model is not None:
            return self._model
        try:
            # lazy: heavy third-party
            from vosk import Model
        except ImportError:
            raise RuntimeError(_missing_vosk_message()) from None
        model_path = get_vosk_model_dir(self._model_name) or await download_vosk_model(
            self._model_name, self._model_url
        )
        try:
            self._model = await asyncio.to_thread(Model, model_path)
        except Exception as e:
            prefix = CFG.ENV_PREFIX
            raise RuntimeError(
                f"Vosk model not found at {model_path}: {e}\n"
                f"Manually download from {self._model_url} or configure\n"
                f"{prefix}_LLM_DICTATION_VOSK_MODEL_NAME / "
                f"{prefix}_LLM_DICTATION_VOSK_MODEL_URL."
            ) from e
        return self._model


def _missing_vosk_message() -> str:
    switch = f"{CFG.ENV_PREFIX}_LLM_DICTATION_BACKEND=openai|google"
    if platform.system() == "Darwin":
        return (
            "vosk is not installed or not compatible with this macOS version.\n"
            "  pip install vosk==0.3.44\n"
            f"Or use a different dictation backend:\n  {switch}"
        )
    return (
        "vosk is not installed.\n"
        "  pip install vosk sounddevice numpy\n"
        f"Or switch backends: {switch}"
    )


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
