def truncate_chars(text: str, max_chars: int) -> str:
    """Hard-cap a string at ``max_chars``, appending an omission marker.

    For clamping single short values (e.g. free-text denial reasons) where
    the directional ``truncate_text`` is overkill.
    """
    if len(text) <= max_chars:
        return text
    omitted = len(text) - max_chars
    return text[:max_chars] + f" ...[TRUNCATED {omitted} chars]"


def truncate_text(text: str, max_chars: int, keep: str = "head") -> tuple[str, bool]:
    """Cap ``text`` at ``max_chars``, truncating from one end.

    ``keep="head"`` keeps the start and drops the overflow at the end, marking
    it ``...[TRUNCATED]`` — for file content, where the top is read first.
    ``keep="tail"`` keeps the end and drops the overflow at the top, marking it
    ``[TRUNCATED]...`` — for shell output, where errors land at the bottom.

    The cut snaps to a line boundary when one is available, so a line is never
    split mid-way. Returns ``(text, truncated)``.
    """
    if len(text) <= max_chars:
        return text, False
    if keep == "tail":
        cut = text[
            len(text) - max_chars :
        ]  # index form: max_chars<=0 -> empty, not whole text
        newline = cut.find("\n")
        if newline != -1:
            cut = cut[newline + 1 :]
        return "[TRUNCATED]...\n" + cut, True
    cut = text[:max_chars]
    newline = cut.rfind("\n")
    if newline > 0:
        cut = cut[:newline]
    return cut + "\n...[TRUNCATED]", True


def truncate_items(items: list, max_chars: int) -> tuple[list, int]:
    """Keep leading ``items`` until their serialized size would exceed
    ``max_chars`` (head-keep). The first item is always kept so a single huge
    entry cannot yield an empty result. Returns ``(kept, omitted_count)``.
    """
    kept: list = []
    total = 0
    for item in items:
        total += len(str(item)) + 1
        if total > max_chars and kept:
            break
        kept.append(item)
    return kept, len(items) - len(kept)
