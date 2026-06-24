import re
import unicodedata

from zrb.builtin.group import case_group
from zrb.context.any_context import AnyContext
from zrb.input.option_input import OptionInput
from zrb.input.str_input import StrInput
from zrb.task.make_task import make_task


def _words(text: str) -> list[str]:
    """Split arbitrary text into lowercase words across case/delimiter boundaries."""
    # Insert a space at camelCase / PascalCase boundaries, then split on any
    # run of non-alphanumeric characters.
    spaced = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", text)
    return [w.lower() for w in re.split(r"[^a-zA-Z0-9]+", spaced) if w]


def _to_case(words: list[str], style: str) -> str:
    if style == "snake":
        return "_".join(words)
    if style == "kebab":
        return "-".join(words)
    if style == "constant":
        return "_".join(w.upper() for w in words)
    if style == "camel":
        return words[0] + "".join(w.capitalize() for w in words[1:]) if words else ""
    if style == "pascal":
        return "".join(w.capitalize() for w in words)
    if style == "title":
        return " ".join(w.capitalize() for w in words)
    raise ValueError(f"Unknown case style: {style}")


@make_task(
    name="convert-case",
    description="🔤 Convert text between snake/camel/pascal/kebab/constant/title case",
    input=[
        StrInput(name="text", description="Text", prompt="Text to convert"),
        OptionInput(
            name="style",
            description="Target case style",
            prompt="Target case",
            default="snake",
            options=["snake", "camel", "pascal", "kebab", "constant", "title"],
        ),
    ],
    group=case_group,
    alias="convert",
)
def convert_case(ctx: AnyContext) -> str:

    result = _to_case(_words(ctx.input.text), ctx.input.style)
    ctx.print(result)
    return result


@make_task(
    name="slugify",
    description="🐌 Turn text into a URL-friendly slug",
    input=StrInput(name="text", description="Text", prompt="Text to slugify"),
    group=case_group,
    alias="slugify",
)
def slugify(ctx: AnyContext) -> str:

    # Strip accents (é -> e) before slugifying for clean ASCII slugs.
    normalized = unicodedata.normalize("NFKD", ctx.input.text)
    ascii_text = normalized.encode("ascii", "ignore").decode()
    result = "-".join(_words(ascii_text))
    ctx.print(result)
    return result
