"""Offline dictation with vosk; the model is downloaded on first use."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import platform
import shutil
import tempfile
from collections.abc import Callable
from typing import Any

from zrb.config.config import CFG
from zrb.llm.dictation.backend.any_dictation_backend import AnyDictationBackend
from zrb.llm.dictation.backend.any_transcription_stream import AnyTranscriptionStream
from zrb.util.async_thread import run_in_daemon

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16000
MEGABYTE = 1 << 20

#: How long the model server may take to answer the connection, whatever the
#: configured download timeout says. ``0`` there means the transfer is not
#: capped, which must not also mean a socket that can wait forever: a thread
#: blocked on one cannot be freed, and would outlive the session that asked.
_CONNECT_TIMEOUT_SECONDS = 30.0


class VoskDownloadLimits:
    """How much a model download may cost, in megabytes.

    A model zip comes from a URL the user configures, so it is untrusted
    input: a hostile or mistyped one can claim any size, and an archive that
    looks small can expand without bound. Every limit is ``0`` for no limit.
    """

    def __init__(
        self,
        max_download_mb: float | None = None,
        max_uncompressed_mb: float | None = None,
        max_file_mb: float | None = None,
        max_files: float | None = None,
    ) -> None:
        prefix = "LLM_DICTATION_VOSK"
        self.max_download = _megabytes(max_download_mb, f"{prefix}_MAX_DOWNLOAD_MB")
        self.max_uncompressed = _megabytes(
            max_uncompressed_mb, f"{prefix}_MAX_UNCOMPRESSED_MB"
        )
        self.max_file = _megabytes(max_file_mb, f"{prefix}_MAX_FILE_MB")
        self.max_files = _count(max_files, f"{prefix}_MAX_FILES")


def _megabytes(value: float | None, knob: str) -> int:
    """Megabytes as bytes; ``None`` reads the knob, ``0`` means no limit."""
    megabytes = getattr(CFG, knob) if value is None else value
    return int(megabytes * MEGABYTE)


def _count(value: float | None, knob: str) -> int:
    """A member count; ``None`` reads the knob, ``0`` means no limit."""
    return int(getattr(CFG, knob) if value is None else value)


class _TooLarge(RuntimeError):
    """A download or archive exceeded one of `VoskDownloadLimits`."""


class VoskDictationBackend(AnyDictationBackend):
    """vosk, offline; *model_name* is downloaded from *model_url* when missing.
    *confidence* is the average word confidence hands-free requires (0-1), 0
    taking every word vosk heard."""

    def __init__(
        self,
        model_name: str = "vosk-model-small-en-us-0.15",
        model_url: str = "https://alphacephei.com/vosk/models",
        download_timeout: float | None = 120.0,
        max_download_mb: float | None = None,
        max_uncompressed_mb: float | None = None,
        max_file_mb: float | None = None,
        max_files: float | None = None,
        confidence: float | None = None,
    ) -> None:
        self._model_name = model_name
        self._model_url = model_url
        self._download_timeout = download_timeout
        self._limits = VoskDownloadLimits(
            max_download_mb, max_uncompressed_mb, max_file_mb, max_files
        )
        self._confidence = confidence or 0.0
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
        await self._download()
        report("Voice model ready")

    async def transcribe(self, audio: bytes) -> str:
        """Everything spoken in *audio*: push-to-talk submits this to the input
        box for the user to edit, so no word of it is dropped as doubtful."""
        return (await self._recognize(audio)).get("text", "")

    async def transcribe_speech(self, audio: bytes) -> str:
        """As `transcribe`, with a transcript vosk heard too faintly dropped:
        hands-free hears the room, and vosk scores what it makes out of noise
        low (*confidence*)."""
        result = await self._recognize(audio)
        if _is_heard_too_faintly(_word_confidences(result), self._confidence):
            return ""
        return result.get("text", "")

    async def _recognize(self, audio: bytes) -> "dict[str, Any]":
        model = await self._get_model()
        # lazy: heavy third-party; after the model, which reports it missing
        from vosk import KaldiRecognizer

        def recognize() -> "dict[str, Any]":
            recognizer = KaldiRecognizer(model, SAMPLE_RATE)
            # vosk omits per-word `conf` from its payload unless asked for it.
            recognizer.SetWords(True)
            if recognizer.AcceptWaveform(audio):
                return json.loads(recognizer.Result())
            return json.loads(recognizer.FinalResult())

        # Decoding takes long enough to freeze the chat UI on the event loop.
        return await run_in_daemon(recognize, name="zrb-vosk-recognizer")

    async def create_stream(self) -> AnyTranscriptionStream:
        model = await self._get_model()
        # lazy: heavy third-party; after the model, which reports it missing
        from vosk import KaldiRecognizer

        recognizer = KaldiRecognizer(model, SAMPLE_RATE)
        # vosk omits per-word `conf` from its payload unless asked for it.
        recognizer.SetWords(True)
        return VoskTranscriptionStream(recognizer, self._confidence)

    async def _get_model(self) -> Any:
        if self._model is not None:
            return self._model
        try:
            # lazy: heavy third-party
            from vosk import Model
        except ImportError:
            raise RuntimeError(_missing_vosk_message()) from None
        model_path = get_vosk_model_dir(self._model_name) or await self._download()
        try:
            self._model = await run_in_daemon(
                Model, model_path, name="zrb-vosk-model-loader"
            )
        except Exception as e:
            prefix = CFG.ENV_PREFIX
            raise RuntimeError(
                f"Vosk model not found at {model_path}: {e}\n"
                f"Manually download from {self._model_url} or configure\n"
                f"{prefix}_LLM_DICTATION_VOSK_MODEL_NAME / "
                f"{prefix}_LLM_DICTATION_VOSK_MODEL_URL."
            ) from e
        return self._model

    async def _download(self) -> str:
        return await download_vosk_model(
            self._model_name,
            self._model_url,
            self._download_timeout,
            self._limits,
        )


class VoskTranscriptionStream(AnyTranscriptionStream):
    """A vosk recognizer fed as the user speaks. vosk returns a finished
    phrase whenever it hears a pause inside the utterance; those are kept,
    and `partial` is them plus the phrase in progress. With *confidence_floor*
    set, `finish` drops a transcript whose words vosk heard too faintly on
    average — which is how it scores what it makes out of noise."""

    def __init__(self, recognizer: Any, confidence_floor: float = 0.0) -> None:
        self._recognizer = recognizer
        self._confidence_floor = confidence_floor
        self._phrases: list[str] = []
        # Every word's confidence, over all the phrases heard so far.
        self._confidences: list[float] = []
        self._in_progress = ""

    @property
    def partial(self) -> str:
        return " ".join([*self._phrases, self._in_progress]).strip()

    async def feed(self, audio: bytes) -> None:
        # Decoding takes long enough to freeze the chat UI on the event loop.
        await asyncio.to_thread(self._accept, audio)

    async def finish(self) -> str:
        final = await asyncio.to_thread(self._recognizer.FinalResult)
        self._in_progress = ""
        payload = json.loads(final)
        self._phrases.append(payload.get("text", ""))
        self._confidences.extend(_word_confidences(payload))
        if _is_heard_too_faintly(self._confidences, self._confidence_floor):
            return ""
        return " ".join(phrase for phrase in self._phrases if phrase).strip()

    def _accept(self, audio: bytes) -> None:
        if self._recognizer.AcceptWaveform(audio):
            payload = json.loads(self._recognizer.Result())
            self._phrases.append(payload.get("text", ""))
            self._confidences.extend(_word_confidences(payload))
            self._in_progress = ""
        else:
            partial = json.loads(self._recognizer.PartialResult())
            self._in_progress = partial.get("partial", "")


def _word_confidences(payload: "dict[str, Any]") -> list[float]:
    """The confidence vosk reported for each word it heard, 0-1 each; none when
    it recognized no words at all."""
    return [float(word.get("conf", 0.0) or 0.0) for word in payload.get("result") or []]


def _is_heard_too_faintly(confidences: list[float], floor: float) -> bool:
    """Whether the words heard average below *floor*: vosk scores what it makes
    out of noise low, so a transcript can be there and still not be speech. No
    words at all, or no floor, is never too faint."""
    if floor <= 0 or not confidences:
        return False
    return sum(confidences) / len(confidences) < floor


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
    model_name: str,
    model_url: str,
    timeout: float | None = 120.0,
    limits: "VoskDownloadLimits | None" = None,
) -> (
    str
):  # noqa: C901 -- registration/factory fn; mccabe sums nested handlers into this line, radon scores each separately (near-trivial on its own)
    """Download and extract a Vosk model, waiting at most *timeout* seconds
    (``0`` or ``None``: the transfer is not capped) for the server to answer.

    The response is streamed to a file in the cache directory rather than
    accumulated in memory, and stopped at ``limits.max_download``. The zip is
    extracted into a private staging directory, checked against *limits*
    before anything is written, and the model moved into place with one
    rename, so another session never loads a half-extracted model; when two
    download at once, the first rename wins. The staging directory is removed
    on every path out, and so is the archive — by the extractor itself, once it
    is done reading it, rather than only by the caller, which a cancellation
    returns past while the extractor is still using the file.

    An uncapped transfer is still a bounded connection: the socket waits at
    most ``_CONNECT_TIMEOUT_SECONDS`` for the server whatever *timeout* says,
    because a thread blocked on a socket with no timeout cannot be freed and
    would outlive the session that asked for the download.

    The response body is read in 64 KiB chunks with an ``await`` between each,
    so the coroutine is cancellable (``/q`` or Ctrl+C) at chunk boundaries
    instead of blocking on one uninterruptible read. On cancellation the socket
    is closed in ``finally``, releasing the in-flight worker thread.

    Returns the model path on success.
    Raises RuntimeError if the download or extraction fails.
    """
    # lazy: heavy (stdlib) — urllib.request drags in ssl/http, for a one-shot
    # download path.
    import urllib.request as _urllib

    limits = limits or VoskDownloadLimits()
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
        resp = await run_in_daemon(
            lambda: _urllib.urlopen(url, timeout=timeout or _CONNECT_TIMEOUT_SECONDS),
            name="zrb-vosk-download",
            # An open that lands after this wait was given up still owns a
            # socket, so it is closed where it lands rather than left to the
            # collector, which would hold that socket until it ran.
            on_orphan=_close_response_quietly,
        )
    except Exception as exc:
        raise _download_error(exc) from exc

    download, zip_path = tempfile.mkstemp(
        prefix=f".{model_name}-", suffix=".zip", dir=cache
    )
    try:
        downloaded = 0
        try:
            with os.fdopen(download, "wb") as sink:
                while True:
                    # CancelledError (BaseException) skips `except Exception`
                    # below and propagates, running `finally` to close the
                    # socket — the abort path.
                    chunk = await run_in_daemon(
                        resp.read, 1 << 16, name="zrb-vosk-download-read"
                    )
                    if not chunk:
                        break
                    downloaded += len(chunk)
                    if limits.max_download and downloaded > limits.max_download:
                        raise _TooLarge(
                            f"{model_name}.zip is larger than the "
                            f"{_mb(limits.max_download)} MB limit "
                            f"({CFG.ENV_PREFIX}_LLM_DICTATION_VOSK_MAX_DOWNLOAD_MB); "
                            f"it had already sent {_mb(downloaded)} MB."
                        )
                    sink.write(chunk)
        except _TooLarge:
            raise
        except Exception as exc:
            raise _download_error(exc) from exc
        finally:
            resp.close()

        await run_in_daemon(
            _extract_model,
            zip_path,
            cache,
            model_name,
            limits,
            name="zrb-vosk-model-extractor",
        )
    finally:
        # The extractor removes the archive itself once it is done with it, and
        # this is the backstop for the paths where no worker ever got the file.
        # It cannot be the only removal: cancelling returns while the extractor
        # is still reading the archive, and an open file cannot be deleted on
        # every platform, where this one then fails silently.
        _remove_quietly(zip_path)

    if not os.path.isdir(target_dir):
        raise RuntimeError(
            f"Downloaded model zip did not produce expected directory {target_dir}.\n"
            f"Manually download {model_name}.zip from {model_url}/\n"
            f"and extract to {cache}/"
        )

    logger.info("Vosk model downloaded to %s", target_dir)
    return target_dir


def _extract_model(
    zip_path: str, cache: str, model_name: str, limits: "VoskDownloadLimits"
) -> None:
    # lazy: heavy (stdlib) — zipfile drags in lzma/bz2, for a one-shot path.
    import zipfile

    target_dir = os.path.join(cache, model_name)
    staging = tempfile.mkdtemp(prefix=f".{model_name}-", dir=cache)
    try:
        real_staging = os.path.realpath(staging)
        with zipfile.ZipFile(zip_path) as zf:
            members = zf.infolist()
            _check_archive(members, staging, real_staging, limits)
            zf.extractall(staging)
        staged_model = os.path.join(staging, model_name)
        if os.path.isdir(staged_model) and not os.path.isdir(target_dir):
            try:
                os.rename(staged_model, target_dir)
            except OSError:
                # Another session renamed its copy into place first.
                pass
    finally:
        shutil.rmtree(staging, ignore_errors=True)
        # Removing the archive is this worker's to do, rather than something the
        # caller does once it stops waiting. A cancelled download returns while
        # this is still reading the zip, and an open file cannot be deleted on
        # every platform: the caller's removal is the one that fails there, and
        # nothing else would ever come back for the file.
        _remove_quietly(zip_path)


def _check_archive(
    members: "list[Any]", staging: str, real_staging: str, limits: "VoskDownloadLimits"
) -> None:
    """Reject an archive that escapes *staging* or costs too much, before
    anything is written.

    The sizes come from the archive's own directory, which is as untrusted as
    the rest of it — that is the point. What makes the check sufficient is that
    `zipfile` reads no more than the declared size of a member and verifies its
    CRC, so a member cannot write more than it declared.
    """
    if limits.max_files and len(members) > limits.max_files:
        raise _TooLarge(
            f"Vosk model archive has {len(members)} files, over the "
            f"{limits.max_files} limit "
            f"({CFG.ENV_PREFIX}_LLM_DICTATION_VOSK_MAX_FILES)."
        )
    total = 0
    for member in members:
        member_path = os.path.realpath(os.path.join(staging, member.filename))
        if member_path != real_staging and not member_path.startswith(
            real_staging + os.sep
        ):
            raise RuntimeError(
                f"Refusing to extract Vosk model: unsafe path in "
                f"archive member {member.filename!r}"
            )
        total += member.file_size
        if limits.max_file and member.file_size > limits.max_file:
            raise _TooLarge(
                f"Vosk model archive member {member.filename!r} unpacks to "
                f"{_mb(member.file_size)} MB, over the {_mb(limits.max_file)} MB "
                f"per-file limit "
                f"({CFG.ENV_PREFIX}_LLM_DICTATION_VOSK_MAX_FILE_MB)."
            )
    if limits.max_uncompressed and total > limits.max_uncompressed:
        raise _TooLarge(
            f"Vosk model archive unpacks to {_mb(total)} MB, over the "
            f"{_mb(limits.max_uncompressed)} MB limit "
            f"({CFG.ENV_PREFIX}_LLM_DICTATION_VOSK_MAX_UNCOMPRESSED_MB)."
        )


def _mb(size: int) -> str:
    # `:g`, so a sub-megabyte overage does not read as "0 MB".
    return f"{size / MEGABYTE:g}"


def _remove_quietly(path: str) -> None:
    try:
        os.remove(path)
    except OSError:
        pass


def _close_response_quietly(response: object) -> None:
    """Close a response that arrived after the wait for it was given up.

    Cancelling the download cannot stop ``urlopen`` already running in a thread
    of its own, so a connection it opens is still opened — a socket held against
    a caller that is gone. Closing it here is what gives that socket back; the
    alternative is the collector, which gets to it whenever it gets to it.

    Nothing is reported, and nothing is raised: the download this belonged to
    failed with the caller's own cancellation, and a socket that cannot be
    closed at that point is not news the caller can act on.
    """
    close = getattr(response, "close", None)
    if close is None:
        return
    try:
        close()
    except OSError:
        pass
