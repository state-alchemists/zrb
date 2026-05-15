"""Describe binary attachments via a multimodal sub-agent.

Used as a fallback when the main agent's model is text-only but the user
attached an image/audio/video. We spawn a one-shot agent with the
configured `LLMConfig.multimodal_model`, hand it the binary, and inline
the resulting text into the user message in place of the attachment.

Only images and audio are described — video is rejected here because most
multimodal models reject video too, and ad-hoc frame extraction is out of
scope. Callers receive `None` for unsupported modalities and should drop
the attachment with a warning.
"""

from __future__ import annotations

from typing import Any

from zrb.config.config import CFG
from zrb.llm.prompt.prompt import get_prompt
from zrb.llm.util.modality import (
    is_known_model,
    media_type_modality,
    supports_modality,
)


async def describe_binary_attachment(
    binary: "Any",
    multimodal_model: "str | Any | None" = None,
) -> str | None:
    """Describe a `BinaryContent` via the supplied multimodal model.

    The caller must pass an explicit *multimodal_model* — this function does
    not consult `LLMConfig.multimodal_model`. That keeps the data flow
    explicit (the runner resolves the global once and forwards it) and makes
    tests independent of environment state.

    Returns the description text on success, ``None`` when:
    - the modality cannot be described (e.g. video),
    - *multimodal_model* is ``None``,
    - the supplied model does not support the binary's modality, or
    - the sub-agent run fails.
    """
    media_type = getattr(binary, "media_type", "") or ""
    modality = media_type_modality(media_type)
    if modality not in ("image", "audio"):
        return None

    if multimodal_model is None:
        return None

    if not supports_modality(multimodal_model, modality):
        CFG.LOGGER.warning(
            f"Multimodal model does not support {modality}; cannot describe attachment."
        )
        return None

    # lazy: avoid importing the agent stack at module-top — this util is
    # imported from the runner, and the runner is loaded transitively by
    # zrb.llm.agent's package __init__.
    from zrb.llm.agent import create_agent, run_agent
    from zrb.llm.config.config import llm_config
    from zrb.llm.config.limiter import llm_limiter

    system_prompt = (
        get_prompt("multimodal_image")
        if modality == "image"
        else get_prompt("multimodal_audio")
    )
    instruction = (
        "Describe the attached image."
        if modality == "image"
        else "Transcribe / describe the attached audio."
    )

    try:
        agent = create_agent(
            model=llm_config.resolve_model(multimodal_model),
            system_prompt=system_prompt,
            yolo=True,  # no tools, no approvals needed
        )
        result, _ = await run_agent(
            agent=agent,
            message=instruction,
            message_history=[],
            limiter=llm_limiter,
            attachments=[binary],
        )
        text = str(result).strip()
        return text or None
    except Exception as exc:
        CFG.LOGGER.warning(f"Multimodal describe failed: {exc}")
        return None


async def replace_unsupported_attachments(
    prompt_content: "str | list[Any] | None",
    main_model: "str | Any | None",
    multimodal_model: "str | Any | None" = None,
    print_fn=None,
) -> "str | list[Any] | None":
    """Substitute / drop binaries the main model cannot consume.

    For each `BinaryContent` in *prompt_content*:
    - If the main model supports the modality → keep as-is.
    - Else, if a multimodal model can describe it → run the describe sub-agent
      and replace the binary with `[<media_type> attachment description: ...]`.
    - Else → drop the attachment and warn via *print_fn*.

    Strings and unknown content types are passed through unchanged.
    """
    if prompt_content is None or isinstance(prompt_content, str):
        return prompt_content
    if not isinstance(prompt_content, list):
        return prompt_content

    # lazy: pydantic_ai is heavy and only needed when binaries are present.
    try:
        from pydantic_ai.messages import BinaryContent
    except ImportError:
        return prompt_content

    out: list[Any] = []
    notify = print_fn or (lambda *a, **k: None)
    main_model_known = is_known_model(main_model)
    for item in prompt_content:
        if not isinstance(item, BinaryContent):
            out.append(item)
            continue
        media_type = getattr(item, "media_type", "") or ""
        modality = media_type_modality(media_type)
        if modality is None:
            out.append(item)
            continue
        # If we can't identify the main model (e.g. MagicMock in tests, or a
        # custom Model object without a recognisable name), don't second-guess —
        # pass through and let the provider decide.
        if not main_model_known:
            out.append(item)
            continue
        if supports_modality(main_model, modality):
            out.append(item)
            continue

        described = await describe_binary_attachment(item, multimodal_model)
        if described:
            tag = modality.capitalize()
            out.append(f"[{tag} attachment ({media_type}) description: {described}]")
            notify(
                f"\n  📝 {tag} attachment described via multimodal model "
                f"({len(described)} chars).\n"
            )
        else:
            reason = _reason_for_drop(modality, multimodal_model)
            notify(
                f"\n  ⚠️  Dropped {modality} attachment ({media_type}): "
                f"main model is text-only and {reason}.\n"
            )

    # Collapse to plain string when only text remains.
    if all(isinstance(x, str) for x in out):
        return "\n".join(x for x in out if x)
    return out


def _reason_for_drop(modality: str, multimodal_model: Any | None) -> str:
    """Return a human-readable explanation of why *modality* was dropped."""
    if multimodal_model is None and modality in ("image", "audio"):
        return "no LLM_MULTIMODAL_MODEL configured"
    if modality in ("image", "audio"):
        return f"{modality} not supported by configured multimodal model"
    return f"{modality} attachments cannot be auto-described"
