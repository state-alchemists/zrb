"""Utilities for handling thinking tags in LLM responses."""

from typing import Literal


def remove_thinking_tags(text: str) -> str:
    """Remove <thinking>...</thinking> and <thought>...</thought> tags with proper nesting handling.

    This function handles:
    - Nested tags (e.g., <thinking><thinking>inner</thinking></thinking>)
    - Unclosed tags (preserves them as text)
    - Multiple tags in the same text
    - Both <thinking> and <thought> tags

    Args:
        text: The text containing thinking/thought tags to clean.

    Returns:
        The text with thinking/thought tags removed.

    Examples:
        >>> remove_thinking_tags("Hello<thinking>I'm thinking</thinking>World")
        'HelloWorld'
        >>> remove_thinking_tags("A<thinking>B<thinking>C</thinking>B</thinking>D")
        'AD'
        >>> remove_thinking_tags("Hello<thinking>Unclosed")
        'Hello<thinking>Unclosed'
    """
    return _remove_tags_for_names(text, ["thinking", "thought"])


def _remove_tags_for_names(text: str, tag_names: list[str]) -> str:
    """Remove tags for multiple tag names with proper nesting handling."""

    def remove_tags_for_name(text: str, tag_name: str) -> str:
        """Remove <tag_name>...</tag_name> tags with proper nesting handling."""
        open_tag = f"<{tag_name}>"
        close_tag = f"</{tag_name}>"
        open_len = len(open_tag)
        close_len = len(close_tag)

        result = []
        i = 0
        n = len(text)

        while i < n:
            # Check for opening tag
            if text.startswith(open_tag, i):
                # Find matching closing tag
                depth = 1
                j = i + open_len
                while j < n and depth > 0:
                    if text.startswith(open_tag, j):
                        depth += 1
                        j += open_len
                    elif text.startswith(close_tag, j):
                        depth -= 1
                        if depth == 0:
                            # Found matching closing tag
                            i = j + close_len
                            break
                        j += close_len
                    else:
                        j += 1
                else:
                    # No matching closing tag found, treat opening tag as text
                    result.append(open_tag)
                    i += open_len
            # Check for closing tag without opening (preserve as text)
            elif text.startswith(close_tag, i):
                result.append(close_tag)
                i += close_len
            else:
                # Regular character
                result.append(text[i])
                i += 1

        return "".join(result)

    # Remove tags for each tag name
    for tag_name in tag_names:
        text = remove_tags_for_name(text, tag_name)

    return text
