"""Tests for render_markdown's CFG-driven theme."""

from zrb.util.cli.markdown import render_markdown


class TestRenderMarkdown:
    def test_renders_content(self):
        out = render_markdown("# Title\n\nbody `code` [x](http://e)")
        assert "Title" in out
        assert "body" in out

    def test_cfg_markdown_style_affects_output(self, monkeypatch):
        # Same source rendered with two different code styles must differ,
        # proving the CFG knob (not a hardcoded theme) drives the output.
        md = "inline `snippet` here"
        monkeypatch.setenv("ZRB_LLM_UI_STYLE_MARKDOWN_CODE", "bold red")
        red = render_markdown(md)
        monkeypatch.setenv("ZRB_LLM_UI_STYLE_MARKDOWN_CODE", "bold green")
        green = render_markdown(md)
        assert red != green

    def test_explicit_theme_bypasses_cfg(self, monkeypatch):
        # Passing a theme object short-circuits the CFG path.
        from rich.theme import Theme

        monkeypatch.setenv("ZRB_LLM_UI_STYLE_MARKDOWN_CODE", "bold red")
        explicit = render_markdown("`x`", theme=Theme({"markdown.code": "bold green"}))
        cfg_driven = render_markdown("`x`")
        assert explicit != cfg_driven

    def test_math_conversion_toggle(self, monkeypatch):
        monkeypatch.setenv("ZRB_LLM_UI_ENABLE_MARKDOWN_MATH", "off")
        off = render_markdown(r"$\alpha$")
        assert r"$\alpha$" in off

        monkeypatch.setenv("ZRB_LLM_UI_ENABLE_MARKDOWN_MATH", "on")
        on = render_markdown(r"$\alpha$")
        assert "α" in on

    def test_math_conversion_ignores_fenced_code(self):
        # A `$` inside a fenced code block (e.g. a diff/tool-call preview)
        # must survive untouched all the way through to the rendered output.
        out = render_markdown("```bash\necho $HOME\n```")
        assert "$HOME" in out

    def test_mermaid_conversion_toggle(self, monkeypatch):
        md = "```mermaid\ngraph TD\n    A --> B\n```"

        monkeypatch.setenv("ZRB_LLM_UI_ENABLE_MARKDOWN_MERMAID", "off")
        off = render_markdown(md)
        assert "graph TD" in off

        monkeypatch.setenv("ZRB_LLM_UI_ENABLE_MARKDOWN_MERMAID", "on")
        on = render_markdown(md)
        assert "graph TD" not in on
        assert "A" in on and "B" in on

    def test_mermaid_conversion_ignores_non_mermaid_fence(self):
        out = render_markdown("```bash\necho $HOME\n```")
        assert "$HOME" in out

    def test_mermaid_diagram_survives_a_narrower_width(self):
        # Simulates a terminal resize: `rewrap_output` re-renders the same
        # source at the new (narrower) width. Before the diagram shrank to
        # fit, Rich word-wrapped wide box-drawing lines mid-character at a
        # narrow width, splitting them into extra, misaligned lines. Each
        # line the shrink-to-fit step produces must survive as one
        # contiguous, unbroken line in the final rendered output.
        import re as _re

        from zrb.util.cli.mermaid_diagram import convert_mermaid_to_art

        md = (
            "```mermaid\ngraph TD\n"
            "    A[Node One] --> B{Check}\n"
            "    B -->|Yes| C[Continue]\n"
            "    B -->|No| D[Abort]\n```"
        )
        narrow_width = 30

        shrunk = convert_mermaid_to_art(md, width=narrow_width)
        diagram_lines = [
            line
            for line in shrunk.split("```\n", 1)[1].rsplit("\n```", 1)[0].splitlines()
            if line.strip()
        ]

        out = render_markdown(md, width=narrow_width)
        plain = _re.sub(r"\x1b\[[0-9;]*m", "", out)
        for line in diagram_lines:
            assert line in plain
