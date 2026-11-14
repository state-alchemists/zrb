"""Repairing a stored message payload until a provider will accept it.

A history file holds what `ModelMessagesTypeAdapter.dump_python` wrote, and that
is a provider's own vocabulary — `part_kind`, `tool_name`, `content` — so a file
written by an older zrb, by a different provider, or by hand can hold a shape no
current validator accepts. This module is the one place that knows those shapes.
A part kind that appears, or is renamed, is a change here, and the file store
does not move.

The two passes run in a fixed order, and the order is the point: content is
cleaned first, because cleaning can leave a part with nothing in it, and the
empty pass then drops the request or response that holds no part at all. In the
other order an emptied part would reach the validator, and the provider would
refuse the whole history over it.
"""

from typing import Any

from zrb.util.string.conversion import to_string

#: Every part whose content is prose: whatever arrives is coerced to a string.
_TEXT_LIKE_PART_KINDS = (
    "text",
    "system-prompt",
    "thinking",
    "retry-prompt",
    "retry-feedback",
)

# The `kind` of every pydantic-ai `UserContent` that is not a plain string.
_USER_CONTENT_KINDS = frozenset(
    {
        "binary",
        "image-url",
        "audio-url",
        "video-url",
        "document-url",
        "text-content",
        "uploaded-file",
        "cache-point",
    }
)


def sanitize_history(data: Any) -> Any:
    """*data*, repaired so a provider validates it: content first, then empties.

    The one call a store makes on the way in and on the way out, so the order
    of the two passes is stated here rather than at each call site.
    """
    return filter_empty_responses(clean_corrupted_content(data))


def clean_corrupted_content(data: Any) -> Any:
    """*data* with every message part's content made valid, recursively.

    A part whose `part_kind` this module does not know keeps its own fields,
    cleaned one level down: an unknown kind is a part zrb has not been taught
    yet, not a corrupted one, and dropping it would lose a turn a provider may
    still replay.
    """
    if isinstance(data, dict):
        part_kind = data.get("part_kind")
        if part_kind == "user-prompt":
            return _clean_user_prompt_part(data)
        if part_kind in _TEXT_LIKE_PART_KINDS:
            return _clean_text_like_part(part_kind, data)
        if part_kind == "tool-return":
            return _clean_tool_return_part(data)
        if part_kind == "tool-call":
            return _clean_tool_call_part(data)
        return {
            key: clean_corrupted_content(value)
            for key, value in data.items()
            if value is not None
        }
    if isinstance(data, list):
        return [
            item
            for item in (clean_corrupted_content(item) for item in data)
            if item is not None
        ]
    return data


def filter_empty_responses(data: Any) -> Any:
    """*data* without a request or response that no longer holds a part.

    A request or response whose parts all failed validation is not a turn a
    provider can replay — its `parts` list would be empty, which the validator
    refuses — so the whole message goes. Every other value keeps its own shape,
    minus the keys whose value came out None.
    """
    if isinstance(data, list):
        filtered = []
        for item in data:
            if not isinstance(item, dict):
                filtered.append(filter_empty_responses(item))
                continue
            parts = item.get("parts")
            if item.get("kind") in ("request", "response") and isinstance(parts, list):
                kept = [part for part in parts if _is_valid_message_part(part)]
                if not kept:
                    continue
                item = {**item, "parts": kept}
            filtered.append(
                {key: filter_empty_responses(value) for key, value in item.items()}
            )
        return filtered
    if isinstance(data, dict):
        cleaned = {}
        for key, value in data.items():
            result = filter_empty_responses(value)
            if result is not None:
                cleaned[key] = result
        return cleaned
    return data


def _is_valid_message_part(part: Any) -> bool:
    """Whether *part* carries something a provider can replay."""
    if not isinstance(part, dict):
        return part is not None
    part_kind = part.get("part_kind")
    if part_kind == "tool-call":
        return part.get("tool_name") is not None
    if "content" in part:
        content = part.get("content")
        return content is not None and content != ""
    return part_kind is not None


# Preserve unknown fields; provider replay may require them.
def _clean_user_prompt_part(data: dict[str, Any]) -> dict[str, Any]:
    content = data.get("content")
    if content is None:
        content = ""
    elif isinstance(content, list):
        if not all(_is_user_content_item(item) for item in content):
            content = to_string(content)
    elif not isinstance(content, str):
        content = to_string(content)
    return {**data, "part_kind": "user-prompt", "content": content}


def _clean_text_like_part(part_kind: str, data: dict[str, Any]) -> dict[str, Any]:
    content = data.get("content")
    if not isinstance(content, str):
        content = to_string(content) if content is not None else ""
    return {**data, "part_kind": part_kind, "content": content}


def _clean_tool_return_part(data: dict[str, Any]) -> dict[str, Any]:
    content = data.get("content")
    if content is None:
        content = ""
    res = {**data, "part_kind": "tool-return", "content": content}
    if not res.get("tool_name"):
        res["tool_name"] = "unknown"
    # Drop null/empty correlation fields that would fail provider validation,
    # while leaving any genuine value (and all other fields) untouched.
    if not res.get("tool_call_id"):
        res.pop("tool_call_id", None)
    if not res.get("timestamp"):
        res.pop("timestamp", None)
    return res


def _clean_tool_call_part(data: dict[str, Any]) -> dict[str, Any] | None:
    tool_name = data.get("tool_name")
    if tool_name is None:
        return None
    res = {**data, "part_kind": "tool-call", "tool_name": tool_name}
    if res.get("args") is None:
        res["args"] = {}
    if not res.get("tool_call_id"):
        res.pop("tool_call_id", None)
    return res


def _is_user_content_item(item: object) -> bool:
    """A string or a dumped attachment: kept as is, never flattened to text.

    Flattening an image wrote its base64 into the prompt as ~450k characters
    of text, which the next turn sent to the model and the limiter could not
    fit in a minute's budget.
    """
    if isinstance(item, str):
        return True
    return isinstance(item, dict) and item.get("kind") in _USER_CONTENT_KINDS
