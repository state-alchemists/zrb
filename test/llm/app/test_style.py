"""create_style() composes a prompt_toolkit Style from CFG.LLM_UI_STYLE_* knobs.

Each test sets the relevant env var(s) directly and checks the resulting
style_rules reflect them live, the way test_config_theme.py checks CFG itself.
"""

from prompt_toolkit.styles import Style

from zrb.llm.app.style import create_style


def _rules(style: Style) -> dict:
    return dict(style.style_rules)


def test_create_style_returns_a_style_instance():
    assert isinstance(create_style(), Style)


def test_direct_passthrough_keys_reflect_their_cfg_knob(monkeypatch):
    monkeypatch.setenv("ZRB_LLM_UI_STYLE_TITLE_BAR", "red")
    monkeypatch.setenv("ZRB_LLM_UI_STYLE_INFO_BAR", "green")
    monkeypatch.setenv("ZRB_LLM_UI_STYLE_FRAME", "blue")
    monkeypatch.setenv("ZRB_LLM_UI_STYLE_FRAME_LABEL", "yellow")
    monkeypatch.setenv("ZRB_LLM_UI_STYLE_INPUT_FRAME", "cyan")
    monkeypatch.setenv("ZRB_LLM_UI_STYLE_THINKING", "magenta")
    monkeypatch.setenv("ZRB_LLM_UI_STYLE_CONFIRMATION", "white")
    monkeypatch.setenv("ZRB_LLM_UI_STYLE_FAINT", "black")
    monkeypatch.setenv("ZRB_LLM_UI_STYLE_OUTPUT_FIELD", "ansired")
    monkeypatch.setenv("ZRB_LLM_UI_STYLE_INPUT_FIELD", "ansigreen")
    monkeypatch.setenv("ZRB_LLM_UI_STYLE_TEXT", "ansiblue")
    monkeypatch.setenv("ZRB_LLM_UI_STYLE_STATUS", "ansiyellow")
    monkeypatch.setenv("ZRB_LLM_UI_STYLE_BOTTOM_TOOLBAR", "ansicyan")

    rules = _rules(create_style())

    assert rules["title-bar"] == "red"
    assert rules["info-bar"] == "green"
    assert rules["frame"] == "blue"
    # "output-frame" is deliberately the same knob as "frame" (no separate
    # LLM_UI_STYLE_OUTPUT_FRAME CFG knob exists).
    assert rules["output-frame"] == "blue"
    assert rules["frame.label"] == "yellow"
    assert rules["input-frame"] == "cyan"
    assert rules["thinking"] == "magenta"
    assert rules["confirmation"] == "white"
    assert rules["faint"] == "black"
    assert rules["output_field"] == "ansired"
    assert rules["input_field"] == "ansigreen"
    assert rules["text"] == "ansiblue"
    assert rules["status"] == "ansiyellow"
    assert rules["bottom-toolbar"] == "ansicyan"


def test_style_is_recomputed_live_from_cfg_not_cached(monkeypatch):
    monkeypatch.setenv("ZRB_LLM_UI_STYLE_STATUS", "red")
    first = _rules(create_style())["status"]
    monkeypatch.setenv("ZRB_LLM_UI_STYLE_STATUS", "blue")
    second = _rules(create_style())["status"]
    assert first == "red"
    assert second == "blue"


def test_title_text_combines_title_bar_bg_and_title_bar(monkeypatch):
    monkeypatch.setenv("ZRB_LLM_UI_STYLE_TITLE_BAR_BG", "ansipurple")
    monkeypatch.setenv("ZRB_LLM_UI_STYLE_TITLE_BAR", "white")
    rules = _rules(create_style())
    assert rules["title-text"] == "bg:ansipurple white"


def test_choice_selected_combines_selected_bg_text_and_bold(monkeypatch):
    monkeypatch.setenv("ZRB_LLM_UI_STYLE_CHOICE_SELECTED_BG", "ansiwhite")
    monkeypatch.setenv("ZRB_LLM_UI_STYLE_TEXT", "black")
    rules = _rules(create_style())
    assert rules["choice.selected"] == "bg:ansiwhite black bold"


def test_choice_desc_and_hint_combine_choice_bg_and_faint(monkeypatch):
    monkeypatch.setenv("ZRB_LLM_UI_STYLE_CHOICE_BG", "ansiblack")
    monkeypatch.setenv("ZRB_LLM_UI_STYLE_FAINT", "white")
    rules = _rules(create_style())
    assert rules["choice.desc"] == "bg:ansiblack white"
    assert rules["choice.hint"] == "bg:ansiblack white"


def test_choice_frame_combines_choice_bg_and_input_frame(monkeypatch):
    monkeypatch.setenv("ZRB_LLM_UI_STYLE_CHOICE_BG", "ansiblack")
    monkeypatch.setenv("ZRB_LLM_UI_STYLE_INPUT_FRAME", "cyan")
    rules = _rules(create_style())
    assert rules["choice-frame"] == "bg:ansiblack cyan"
