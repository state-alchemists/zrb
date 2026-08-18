from prompt_toolkit.styles import Style

from zrb.config.config import CFG


def create_style() -> Style:
    choice_bg = CFG.LLM_UI_STYLE_CHOICE_BG
    choice_selected_bg = CFG.LLM_UI_STYLE_CHOICE_SELECTED_BG
    text = CFG.LLM_UI_STYLE_TEXT
    faint = CFG.LLM_UI_STYLE_FAINT
    return Style.from_dict(
        {
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
            # AskUserQuestion selection widget. An opaque panel background stops
            # the streaming output behind the float from showing through.
            "choice-frame": f"bg:{choice_bg} {CFG.LLM_UI_STYLE_INPUT_FRAME}",
            "choice": f"bg:{choice_bg}",
            "choice.question": f"bg:{choice_bg} bold",
            "choice.selected": f"bg:{choice_selected_bg} {text} bold",
            "choice.option": f"bg:{choice_bg}",
            "choice.desc": f"bg:{choice_bg} {faint}",
            "choice.hint": f"bg:{choice_bg} {faint}",
            # Sub-agent picker (UIAgentPicker). Same panel look, reusing the
            # same CFG style knobs — no new config for a cosmetic sibling.
            "agent-picker-frame": f"bg:{choice_bg} {CFG.LLM_UI_STYLE_INPUT_FRAME}",
            "agent-picker": f"bg:{choice_bg}",
            "agent-picker.question": f"bg:{choice_bg} bold",
            "agent-picker.selected": f"bg:{choice_selected_bg} {text} bold",
            "agent-picker.option": f"bg:{choice_bg}",
            "agent-picker.desc": f"bg:{choice_bg} {faint}",
            "agent-picker.hint": f"bg:{choice_bg} {faint}",
            "agent-picker.needs-approval": (
                f"bg:{choice_bg} {CFG.LLM_UI_STYLE_CONFIRMATION} bold"
            ),
        }
    )
