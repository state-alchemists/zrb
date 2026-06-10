from prompt_toolkit.styles import Style

from zrb.config.config import CFG

# Panel background for the AskUserQuestion selection widget, and the highlight
# bar for the row under the cursor. Kept dark to read as a card over the chat.
_CHOICE_BG = "#1f1f1f"
_CHOICE_SELECTED_BG = "#264f78"


def create_style() -> Style:
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
            # AskUserQuestion selection widget. An opaque panel background stops
            # the streaming output behind the float from showing through.
            "choice-frame": f"bg:{_CHOICE_BG} {CFG.LLM_UI_STYLE_INPUT_FRAME}",
            "choice": f"bg:{_CHOICE_BG}",
            "choice.question": f"bg:{_CHOICE_BG} bold",
            "choice.selected": f"bg:{_CHOICE_SELECTED_BG} #ffffff bold",
            "choice.option": f"bg:{_CHOICE_BG}",
            "choice.desc": f"bg:{_CHOICE_BG} #888888",
            "choice.hint": f"bg:{_CHOICE_BG} #6c6c6c",
        }
    )
