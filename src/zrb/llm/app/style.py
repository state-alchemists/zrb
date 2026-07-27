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
            # Class for the HTML-rendered title bar, so those values reach
            # prompt-toolkit as *styles*: inlining them into an HTML
            # `color=`/`bg=` attribute accepts only a bare color, and any real
            # style string ("bold #ff0000") raised `ValueError: "fg" attribute
            # contains a space` while building the layout. A Style dict takes the
            # full grammar.
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
        }
    )
