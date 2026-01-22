from prompt_toolkit.styles import Style

from zrb.config.config import CFG


def create_style() -> Style:
    return Style.from_dict(
        {
            "title-bar": CFG.LLM_UI_STYLE_TITLE_BAR,
            "info-bar": CFG.LLM_UI_STYLE_INFO_BAR,
            "frame": CFG.LLM_UI_STYLE_FRAME,
            "frame.label": CFG.LLM_UI_STYLE_FRAME_LABEL,
            "input-frame": CFG.LLM_UI_STYLE_INPUT_FRAME,
            "thinking": CFG.LLM_UI_STYLE_THINKING,
            "faint": CFG.LLM_UI_STYLE_FAINT,
            "output_field": CFG.LLM_UI_STYLE_OUTPUT_FIELD,
            "input_field": CFG.LLM_UI_STYLE_INPUT_FIELD,
            "text": CFG.LLM_UI_STYLE_TEXT,
            "status": CFG.LLM_UI_STYLE_STATUS,
            "bottom-toolbar": CFG.LLM_UI_STYLE_BOTTOM_TOOLBAR,
        }
    )
