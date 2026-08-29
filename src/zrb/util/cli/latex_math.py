import re
from functools import lru_cache

_FENCED_CODE = re.compile(r"^([`~]{3,})([^\n]*)\n(.*?)^\1[`~]*[ \t]*$", re.M | re.S)
_INLINE_CODE = re.compile(r"`[^`\n]*`")
_BLOCK_MATH = re.compile(r"\$\$(.+?)\$\$", re.S)
# Pandoc-style inline-math heuristic: content must not start/end with
# whitespace (rules out "$5 and $10"), must be non-empty, and the closing `$`
# must not be immediately followed by a digit.
_INLINE_MATH = re.compile(r"(?<!\$)\$(?!\s)(.+?)(?<!\s)\$(?!\$)(?!\d)", re.S)

_PLACEHOLDER = "\x00{}\x00"
_PLACEHOLDER_RE = re.compile(r"\x00(\d+)\x00")

# Unicode has no full super/subscript alphabet (no superscript "q"; subscript
# covers only aehiklmnoprstuvx), so a run converts only when every character
# in it has a mapping -- otherwise it's left as pylatexenc's own ASCII output
# (e.g. "x^2" -> "x²", but "x^q" stays "x^q").
_SUPERSCRIPT = {
    **dict(zip("0123456789", "⁰¹²³⁴⁵⁶⁷⁸⁹")),
    "+": "⁺",
    "-": "⁻",
    "=": "⁼",
    "(": "⁽",
    ")": "⁾",
    "a": "ᵃ",
    "b": "ᵇ",
    "c": "ᶜ",
    "d": "ᵈ",
    "e": "ᵉ",
    "f": "ᶠ",
    "g": "ᵍ",
    "h": "ʰ",
    "i": "ⁱ",
    "j": "ʲ",
    "k": "ᵏ",
    "l": "ˡ",
    "m": "ᵐ",
    "n": "ⁿ",
    "o": "ᵒ",
    "p": "ᵖ",
    "r": "ʳ",
    "s": "ˢ",
    "t": "ᵗ",
    "u": "ᵘ",
    "v": "ᵛ",
    "w": "ʷ",
    "x": "ˣ",
    "y": "ʸ",
    "z": "ᶻ",
}
_SUBSCRIPT = {
    **dict(zip("0123456789", "₀₁₂₃₄₅₆₇₈₉")),
    "+": "₊",
    "-": "₋",
    "=": "₌",
    "(": "₍",
    ")": "₎",
    "a": "ₐ",
    "e": "ₑ",
    "h": "ₕ",
    "i": "ᵢ",
    "k": "ₖ",
    "l": "ₗ",
    "m": "ₘ",
    "n": "ₙ",
    "o": "ₒ",
    "p": "ₚ",
    "r": "ᵣ",
    "s": "ₛ",
    "t": "ₜ",
    "u": "ᵤ",
    "v": "ᵥ",
    "x": "ₓ",
}
_SUPER_SUB_RE = re.compile(r"([\^_])(\{[^{}]*\}|[^\s\^_{}]+)")


def _convert_super_sub(text: str) -> str:
    """Convert `^exp`/`_sub` runs (as left by pylatexenc, braces already
    stripped) to Unicode super/subscript characters, one run at a time."""

    def _replace(match: re.Match) -> str:
        marker, content = match.group(1), match.group(2)
        if content.startswith("{") and content.endswith("}"):
            content = content[1:-1]
        mapping = _SUPERSCRIPT if marker == "^" else _SUBSCRIPT
        if content and all(ch in mapping for ch in content):
            return "".join(mapping[ch] for ch in content)
        return match.group(0)

    return _SUPER_SUB_RE.sub(_replace, text)


@lru_cache(maxsize=1)
def _get_latex_tools():
    # lazy: heavy third-party
    from pylatexenc.latex2text import LatexNodes2Text
    from pylatexenc.latexwalker import LatexWalker, LatexWalkerParseError

    return LatexWalker, LatexWalkerParseError, LatexNodes2Text()


def convert_math_to_unicode(
    text: str,
) -> (
    str
):  # noqa: C901 -- registration/factory fn; mccabe sums nested handlers into this line, radon scores each separately (near-trivial on its own)
    """Convert `$...$` / `$$...$$` LaTeX math spans in `text` to Unicode.

    Fenced code blocks and inline code spans are masked out first, so a `$`
    inside code (shell vars, prices in a snippet, ...) is never touched.
    Anything that can't be safely converted -- masked code, ambiguous "$5 and
    $10" prose, or unparseable/unrecognized LaTeX -- is left exactly as
    written, matching the pre-existing fallback (plain literal text).
    """
    try:
        LatexWalker, LatexWalkerParseError, converter = _get_latex_tools()

        def _convert_span(raw: str, latex_source: str) -> str:
            """Convert one math span's LaTeX source, falling back to `raw`
            (the original span, delimiters included) on any parse/convert
            failure or when the result is suspiciously empty (e.g. an
            unrecognized macro silently dropped instead of raised)."""
            try:
                walker = LatexWalker(latex_source, tolerant_parsing=False)
                nodes, _, _ = walker.get_latex_nodes()
                converted = converter.nodelist_to_text(nodes)
            except LatexWalkerParseError:
                return raw
            except Exception:
                return raw
            if not converted.strip() and latex_source.strip():
                return raw
            return _convert_super_sub(converted)

        protected: list[str] = []

        def _mask(match: re.Match) -> str:
            protected.append(match.group(0))
            return _PLACEHOLDER.format(len(protected) - 1)

        def _mask_fence(match: re.Match) -> str:
            """Mask an ordinary fence unchanged, but a ```latex/```tex fence
            is treated as a math block: rendered and inlined as flowing text
            on success, or left as the original (syntax-highlighted) fence
            when it can't be converted -- same per-span fallback as `$...$`.
            """
            info = (
                match.group(2).strip().split()[0].lower()
                if match.group(2).strip()
                else ""
            )
            if info in ("latex", "tex"):
                body = match.group(3)
                rendered = _convert_span(body, body)
                protected.append(rendered if rendered != body else match.group(0))
            else:
                protected.append(match.group(0))
            return _PLACEHOLDER.format(len(protected) - 1)

        masked = _FENCED_CODE.sub(_mask_fence, text)
        masked = _INLINE_CODE.sub(_mask, masked)

        masked = _BLOCK_MATH.sub(
            lambda m: _convert_span(m.group(0), m.group(1)), masked
        )
        masked = _INLINE_MATH.sub(
            lambda m: _convert_span(m.group(0), m.group(1)), masked
        )

        return _PLACEHOLDER_RE.sub(lambda m: protected[int(m.group(1))], masked)
    except Exception:
        return text
