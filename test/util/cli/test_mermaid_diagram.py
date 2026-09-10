"""Tests for convert_mermaid_to_art's diagram rendering and fallbacks."""

from zrb.util.cli.mermaid_diagram import convert_mermaid_to_art


class TestConvertMermaidToArt:
    def test_converts_mermaid_fence_to_art(self):
        text = "before\n```mermaid\ngraph TD\n    A --> B\n```\nafter"
        out = convert_mermaid_to_art(text)
        assert "```mermaid" not in out
        assert "A" in out and "B" in out
        assert "before" in out and "after" in out

    def test_converts_mmd_alias_fence(self):
        text = "```mmd\ngraph TD\n    A --> B\n```"
        out = convert_mermaid_to_art(text)
        assert "```mmd" not in out
        assert "A" in out and "B" in out

    def test_unparseable_mermaid_falls_back_to_the_fence(self):
        text = "```mermaid\nthis is not a real diagram at all\n```"
        assert convert_mermaid_to_art(text) == text

    def test_non_mermaid_fence_is_untouched(self):
        text = "```bash\necho $HOME\n```"
        assert convert_mermaid_to_art(text) == text

    def test_result_stays_fenced_so_rich_does_not_reflow_it(self):
        text = "```mermaid\ngraph TD\n    A --> B\n```"
        out = convert_mermaid_to_art(text)
        assert out.startswith("```\n")
        assert out.endswith("\n```")

    def test_shrinks_to_fit_a_narrow_width(self):
        # A wide diagram rendered at the default gap/padding must shrink when
        # a target width is given, instead of staying wide and relying on
        # Rich to word-wrap it later (which corrupts the box-drawing art --
        # this is what broke across a terminal resize).
        text = (
            "```mermaid\ngraph TD\n"
            "    A[Node One] --> B{Check}\n"
            "    B -->|Yes| C[Continue]\n"
            "    B -->|No| D[Abort]\n```"
        )
        wide = convert_mermaid_to_art(text, width=200)
        narrow = convert_mermaid_to_art(text, width=30)

        def _max_line_width(rendered: str) -> int:
            body = rendered.split("```\n", 1)[1].rsplit("\n```", 1)[0]
            return max((len(line) for line in body.splitlines()), default=0)

        assert _max_line_width(narrow) < _max_line_width(wide)
        assert _max_line_width(narrow) <= 30 - 2

    def test_no_width_skips_fitting(self):
        # Without a width hint (e.g. a call site that doesn't know the
        # console width), rendering still succeeds at the default size.
        text = "```mermaid\ngraph TD\n    A --> B\n```"
        assert convert_mermaid_to_art(text, width=None) == convert_mermaid_to_art(text)
