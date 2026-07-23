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
