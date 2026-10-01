"""Dictation through the configured multimodal chat model."""

from __future__ import annotations

from typing import Any

from zrb.config.config import CFG
from zrb.llm.dictation.backend.any_dictation_backend import AnyDictationBackend
from zrb.llm.dictation.backend.wav import pcm16_to_wav_bytes


class MultimodalDictationBackend(AnyDictationBackend):
    """A chat model that takes audio, `CFG.LLM_MULTIMODAL_MODEL` by default.

    Works with providers whose pydantic-ai implementation accepts audio as a
    content block (e.g. Google Gemini). OpenAI chat models are rejected: the
    chat completions API does not accept audio content blocks, so the
    ``openai`` backend is the one to use there. It is asked to transcribe
    with *instruction* (default: `CFG.LLM_DICTATION_TRANSCRIBE_PROMPT`).
    """

    def __init__(self, model: Any = None, instruction: str | None = None) -> None:
        self._model = model
        self._instruction = instruction
        self._checked_model: Any = None

    @property
    def name(self) -> str:
        return "multimodal"

    async def transcribe(self, audio: bytes) -> str:
        # lazy: zrb internal (heavy via transitive) — not a cycle, verified
        # empirically (nothing zrb.llm.agent's package __init__ imports at
        # module level reaches zrb.llm.dictation).
        from zrb.llm.agent import create_agent, run_agent
        from zrb.llm.agent.types import BinaryContent
        from zrb.llm.config.limiter import llm_limiter
        from zrb.llm.prompt.prompt import get_prompt

        agent = create_agent(
            model=self._get_model(),
            system_prompt=get_prompt("multimodal_audio"),
            yolo=True,
            resolve_model=False,
        )
        result, _ = await run_agent(
            agent=agent,
            message=self._instruction or CFG.LLM_DICTATION_TRANSCRIBE_PROMPT,
            message_history=[],
            limiter=llm_limiter,
            attachments=[
                BinaryContent(data=pcm16_to_wav_bytes(audio), media_type="audio/wav")
            ],
        )
        return str(result).strip()

    def _get_model(self) -> Any:
        if self._checked_model is not None:
            return self._checked_model
        # lazy: zrb internal (heavy via transitive)
        from zrb.llm.config.model_resolver import resolve_configured_multimodal_model
        from zrb.llm.util.capabilities import model_capabilities

        model = resolve_configured_multimodal_model(self._model)
        prefix = CFG.ENV_PREFIX
        if not model:
            raise RuntimeError(
                "LLM_MULTIMODAL_MODEL is not configured. "
                f"Set {prefix}_LLM_MULTIMODAL_MODEL or switch to a different "
                "dictation backend."
            )
        if is_openai_chat_model(model):
            raise RuntimeError(
                f"Multimodal model {model_name(model)!r} is from OpenAI, which "
                "does not accept audio content blocks in the chat completions "
                "API (pydantic-ai limitation). "
                f"Set {prefix}_LLM_DICTATION_BACKEND=openai to use its "
                f"transcription API, or set {prefix}_LLM_MULTIMODAL_MODEL to a "
                "model that supports inline audio (e.g. gemini-2.5-flash)."
            )
        if not model_capabilities.supports_modality(model, "audio"):
            raise RuntimeError(
                f"Multimodal model {model_name(model)!r} does not support audio "
                f"transcription. Set {prefix}_LLM_DICTATION_BACKEND to one of: "
                "vosk, openai, google, or choose a model that supports audio "
                "input."
            )
        self._checked_model = model
        return model


def is_openai_chat_model(model: object) -> bool:
    """True for OpenAI chat models that cannot receive audio as content blocks.

    Checks both pydantic-ai :class:`~pydantic_ai.models.openai.OpenAIChatModel`
    instances and string model identifiers (``openai:gpt-5.6-luna``, ``gpt-4o``, etc.)
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
