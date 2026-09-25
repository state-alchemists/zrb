from prompt_toolkit.styles import Style

from zrb.config.config import CFG


def create_style() -> Style:
    choice_bg = CFG.LLM_UI_STYLE_CHOICE_BG
    choice_selected_bg = CFG.LLM_UI_STYLE_CHOICE_SELECTED_BG
    text = CFG.LLM_UI_STYLE_TEXT
    faint = CFG.LLM_UI_STYLE_FAINT
    styles = {
        "title-bar": CFG.LLM_UI_STYLE_TITLE_BAR,
        "info-bar": CFG.LLM_UI_STYLE_INFO_BAR,
        "frame": CFG.LLM_UI_STYLE_FRAME,
        "frame.label": CFG.LLM_UI_STYLE_FRAME_LABEL,
        "input-frame": CFG.LLM_UI_STYLE_INPUT_FRAME,
        "output-frame": CFG.LLM_UI_STYLE_FRAME,
        "thinking": CFG.LLM_UI_STYLE_THINKING,
        "confirmation": CFG.LLM_UI_STYLE_CONFIRMATION,
        "faint": CFG.LLM_UI_STYLE_FAINT,
        "output_field": CFG.LLM_UI_STYLE_OUTPUT_FIELD,
        "input_field": CFG.LLM_UI_STYLE_INPUT_FIELD,
        "text": CFG.LLM_UI_STYLE_TEXT,
        "status": CFG.LLM_UI_STYLE_STATUS,
        "bottom-toolbar": CFG.LLM_UI_STYLE_BOTTOM_TOOLBAR,
        "title-text": (
            f"bg:{CFG.LLM_UI_STYLE_TITLE_BAR_BG} {CFG.LLM_UI_STYLE_TITLE_BAR}"
        ),
    }
    # The AskUserQuestion widget and the sub-agent picker share one panel look.
    # The opaque background stops streaming output bleeding through the float.
    for panel in ("choice", "agent-picker"):
        styles.update(
            {
                f"{panel}-frame": f"bg:{choice_bg} {CFG.LLM_UI_STYLE_INPUT_FRAME}",
                panel: f"bg:{choice_bg}",
                f"{panel}.question": f"bg:{choice_bg} bold",
                f"{panel}.selected": f"bg:{choice_selected_bg} {text} bold",
                f"{panel}.option": f"bg:{choice_bg}",
                f"{panel}.desc": f"bg:{choice_bg} {faint}",
                f"{panel}.hint": f"bg:{choice_bg} {faint}",
            }
        )
    styles["agent-picker.needs-approval"] = (
        f"bg:{choice_bg} {CFG.LLM_UI_STYLE_CONFIRMATION} bold"
    )
    return Style.from_dict(styles)
