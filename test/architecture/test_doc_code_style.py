"""Guards the Python samples in live docs against hanging indentation.

The source is formatted by black: a call too long for one line opens its
bracket at the end of the line and puts each argument on its own line, four
spaces in. Doc samples are copied into `zrb_init.py` files as they are, so they
follow the same shape; a sample that hangs arguments under an unclosed call
(`register("x", Spec(` … `))`) or aligns them under the bracket teaches a style
the codebase does not use.

Changelogs are excluded: they are frozen history.
"""

import io
import re
import tokenize
from pathlib import Path

REPO_ROOT = Path(__file__).parents[2]
_FENCE = re.compile(r"^```python\n(.*?)^```", re.S | re.M)
_OPENERS = {"(": ")", "[": "]", "{": "}"}


def _live_docs() -> list[Path]:
    docs = [
        path
        for path in (REPO_ROOT / "docs").rglob("*.md")
        if "changelog" not in path.parts
    ]
    return [REPO_ROOT / "README.md", *sorted(docs)]


def _hanging_lines(source: str) -> list[int]:
    """Lines where a bracket closes on a later line but holds code on its own."""
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))
    except (tokenize.TokenError, IndentationError):
        return []
    stack: list[tuple[tokenize.TokenInfo, int]] = []
    found: list[int] = []
    for index, token in enumerate(tokens):
        if token.type != tokenize.OP:
            continue
        if token.string in _OPENERS:
            stack.append((token, index))
        elif token.string in _OPENERS.values() and stack:
            opener, opener_index = stack.pop()
            if token.start[0] == opener.start[0]:
                continue
            following = tokens[opener_index + 1]
            if following.type not in (tokenize.NL, tokenize.NEWLINE, tokenize.COMMENT):
                found.append(opener.start[0])
    return found


def test_no_doc_sample_hangs_its_arguments():
    offenders = []
    for path in _live_docs():
        text = path.read_text(encoding="utf-8")
        for match in _FENCE.finditer(text):
            first_line = text[: match.start(1)].count("\n") + 1
            for line in _hanging_lines(match.group(1)):
                offenders.append(
                    f"{path.relative_to(REPO_ROOT)}:{first_line + line - 1}"
                )
    assert not offenders, (
        "Doc samples hang arguments after an unclosed bracket; open the bracket "
        "at the end of the line and indent each argument four spaces, as black "
        f"formats the source: {offenders}"
    )
