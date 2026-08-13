"""Tests for convert_math_to_unicode's LaTeX math conversion and fallbacks."""

from zrb.util.cli.latex_math import convert_math_to_unicode


class TestConvertMathToUnicode:
    def test_converts_inline_math(self):
        out = convert_math_to_unicode(r"Greek: $\alpha + \beta$ done.")
        assert out == "Greek: α+ β done."

    def test_converts_block_math(self):
        out = convert_math_to_unicode(r"$$\int_a^b f(x) dx$$")
        assert out == "∫ₐᵇ f(x) dx"

    def test_ignores_dollar_amounts(self):
        text = "I have $5 and $10 in my pocket."
        assert convert_math_to_unicode(text) == text

    def test_preserves_dollar_inside_fenced_code_block(self):
        text = "```bash\necho $HOME and $PATH\n```"
        assert convert_math_to_unicode(text) == text

    def test_preserves_dollar_inside_inline_code_span(self):
        text = "price is `$5` in code"
        assert convert_math_to_unicode(text) == text

    def test_malformed_latex_falls_back_to_raw_span(self):
        text = r"broken $\badcmd{$ stays raw"
        assert convert_math_to_unicode(text) == text

    def test_unrecognized_macro_falls_back_to_raw_span(self):
        text = r"unknown $\unknownmacroxyz$ stays raw"
        assert convert_math_to_unicode(text) == text

    def test_one_bad_span_does_not_affect_a_good_span_in_the_same_text(self):
        text = r"good $\alpha$ but bad $\badcmd{$ here"
        out = convert_math_to_unicode(text)
        assert "α" in out
        assert r"$\badcmd{$" in out

    def test_converts_superscript_and_subscript(self):
        out = convert_math_to_unicode(r"$x^2 + y^2 = z^2$")
        assert out == "x² + y² = z²"

    def test_converts_multi_char_super_and_subscript(self):
        out = convert_math_to_unicode(r"$$\sum_{i=1}^{n} i$$")
        assert out == "∑ᵢ₌₁ⁿ i"

    def test_falls_back_to_ascii_for_unmappable_super_sub_char(self):
        # Unicode has no superscript "q" -- the whole run is left as-is
        # rather than partially/incorrectly converted.
        out = convert_math_to_unicode(r"$x^q$")
        assert out == "x^q"

    def test_does_not_touch_markdown_emphasis_underscores(self):
        # Super/subscript conversion is scoped to detected math spans only,
        # so markdown's `_italic_` syntax outside `$...$` is never touched
        # even when every character happens to be subscript-mappable.
        text = "this is _italic_ and _am_ too"
        assert convert_math_to_unicode(text) == text

    def test_converts_latex_fenced_block(self):
        text = "before\n```latex\n\\frac{a}{b} + \\sqrt{x}\n```\nafter"
        out = convert_math_to_unicode(text)
        assert "a/b" in out
        assert "√(x)" in out
        assert "```" not in out

    def test_converts_tex_fenced_block(self):
        out = convert_math_to_unicode("```tex\nx^2 + \\alpha\n```")
        assert out == "x² + α"

    def test_broken_latex_fenced_block_falls_back_to_the_fence(self):
        text = "```latex\n\\badcmd{\n```"
        assert convert_math_to_unicode(text) == text

    def test_non_latex_fenced_block_is_untouched(self):
        text = "```bash\necho $HOME\n```"
        assert convert_math_to_unicode(text) == text
