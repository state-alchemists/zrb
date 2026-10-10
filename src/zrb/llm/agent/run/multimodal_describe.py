"""Describe binary attachments via a multimodal sub-agent.

Fallback for a text-only main model: a one-shot agent on the multimodal model
describes the binary, and the text replaces the attachment. Only images and
audio are described.
"""

from __future__ import annotations

from typing import Any

from zrb.config.config import CFG
from zrb.llm.prompt.prompt import get_prompt
from zrb.llm.util.capabilities import (
    is_known_model,
    media_type_modality,
    model_capabilities,
)


async def describe_binary_attachment(
    binary: "Any",
    multimodal_model: "str | Any | None" = None,
) -> str | None:
    """Describe a `BinaryContent` via the supplied multimodal model.

    *multimodal_model* is never read from `CFG` here; the caller resolves it.

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

    if not model_capabilities.supports_modality(multimodal_model, modality):
        CFG.LOGGER.warning(
            f"Multimodal model does not support {modality}; cannot describe attachment."
        )
        return None

    # lazy: zrb internal (heavy via transitive) — zrb.llm.agent pulls in the
    # runner, which lazily imports this module.
    from zrb.llm.agent import create_agent, run_agent
    from zrb.llm.config.limiter import get_run_llm_limiter
    from zrb.llm.config.model_resolver import resolve_configured_model

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
            model=resolve_configured_model(multimodal_model),
            system_prompt=system_prompt,
            yolo=True,  # no tools, no approvals needed
            resolve_model=False,
        )
        result, _ = await run_agent(
            agent=agent,
            message=instruction,
            message_history=[],
            limiter=get_run_llm_limiter(),
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

    # lazy: zrb internal (heavy via transitive)
    try:
        from zrb.llm.agent.types import BinaryContent
    except ImportError:
        return prompt_content

    out: list[Any] = []
    notify = print_fn or (lambda *a, **k: None)
    main_model_known = is_known_model(main_model)
    for item in prompt_content:
        out.append(
            await _replace_one_attachment(
                item,
                BinaryContent,
                main_model,
                main_model_known,
                multimodal_model,
                notify,
            )
        )
    out = [entry for entry in out if entry is not None]

    # Collapse to plain string when only text remains.
    if all(isinstance(x, str) for x in out):
        return "\n".join(x for x in out if x)
    return out


async def _replace_one_attachment(
    item: Any,
    binary_content_type: type,
    main_model: "str | Any | None",
    main_model_known: bool,
    multimodal_model: "str | Any | None",
    notify: Any,
) -> Any:
    """`item` itself, a text description of it, or `None` to drop it.

    Non-binaries, unrecognized modalities, and every attachment for an
    unidentifiable main model pass through untouched.
    """
    if not isinstance(item, binary_content_type):
        return item
    media_type = getattr(item, "media_type", "") or ""
    modality = media_type_modality(media_type)
    if modality is None or not main_model_known:
        return item
    if model_capabilities.supports_modality(main_model, modality):
        return item
    described = await describe_binary_attachment(item, multimodal_model)
    if described:
        tag = modality.capitalize()
        notify(
            f"\n  📝 {tag} attachment described via multimodal model "
            f"({len(described)} chars).\n"
        )
        return f"[{tag} attachment ({media_type}) description: {described}]"
    reason = _reason_for_drop(modality, multimodal_model)
    notify(
        f"\n  ❗ Dropped {modality} attachment ({media_type}): "
        f"main model is text-only and {reason}.\n"
    )
    return None


def _reason_for_drop(modality: str, multimodal_model: Any | None) -> str:
    """Return a human-readable explanation of why *modality* was dropped."""
    if multimodal_model is None and modality in ("image", "audio"):
        return "no LLM_MULTIMODAL_MODEL configured"
    if modality in ("image", "audio"):
        return f"{modality} not supported by configured multimodal model"
    return f"{modality} attachments cannot be auto-described"
