"""
Monokai Theme Example

Demonstrates registering a custom style theme with `register_theme` and
selecting it with `ZRB_THEME`.

The key idea: a registered theme is a *partial* palette — it is merged onto the
built-in `dark` theme, so you only list the knobs you want to change. Every knob
you omit (here: the bottom-toolbar reset and the CLI_STYLE_* bold/faint
attributes) keeps its `dark` value instead of blanking out.

Knob names are the `CFG` attribute names without the `ZRB_` prefix. Values are
whatever the knob's consumer expects:
    - LLM UI knobs   -> prompt_toolkit style strings (hex, ansi*, "fg:… bold")
    - MARKDOWN/CLI   -> Rich style strings ("bold #66d9ef underline")

Usage:
    cd examples/themes/monokai
    ZRB_THEME=monokai zrb llm chat
    # or `export ZRB_THEME=monokai` once, then `zrb llm chat`
"""

from zrb.config.theme import register_theme

# https://monokai.pro palette:
#   bg #272822  fg #f8f8f2  comment #75715e  yellow #e6db74  green #a6e22e
#   orange #fd971f  cyan #66d9ef  purple #ae81ff  pink #f92672
register_theme(
    "monokai",
    {
        # --- Frame & bars ---
        "LLM_UI_STYLE_TITLE_BAR": "#272822",
        "LLM_UI_STYLE_TITLE_BAR_BG": "#a6e22e",
        "LLM_UI_STYLE_INFO_BAR": "#f8f8f2",
        "LLM_UI_STYLE_FRAME": "#75715e",
        "LLM_UI_STYLE_FRAME_LABEL": "#e6db74",
        "LLM_UI_STYLE_INPUT_FRAME": "#75715e",
        "LLM_UI_STYLE_PROMPT": "#66d9ef",
        # --- Status & indicators ---
        "LLM_UI_STYLE_THINKING": "#a6e22e",
        "LLM_UI_STYLE_CONFIRMATION": "#e6db74",
        "LLM_UI_STYLE_FAINT": "#75715e",
        "LLM_UI_STYLE_STATUS": "#f8f8f2",
        # --- Text areas ---
        "LLM_UI_STYLE_OUTPUT_FIELD": "#f8f8f2",
        "LLM_UI_STYLE_INPUT_FIELD": "#f8f8f2",
        "LLM_UI_STYLE_TEXT": "#f8f8f2",
        # --- Choice widget (AskUserQuestion panel) ---
        "LLM_UI_STYLE_CHOICE_BG": "#3e3d32",
        "LLM_UI_STYLE_CHOICE_SELECTED_BG": "#49483e",
        # --- Mode badge (Shift+Tab cycle indicator) ---
        "LLM_UI_STYLE_MODE_NORMAL": "fg:#a6e22e",
        "LLM_UI_STYLE_MODE_ACCEPT_EDITS": "fg:#e6db74 bold",
        "LLM_UI_STYLE_MODE_PLAN": "fg:#66d9ef bold",
        "LLM_UI_STYLE_MODE_YOLO": "fg:#f92672 bold",
        "LLM_UI_STYLE_MODE_CUSTOM": "fg:#e6db74 bold",
        # --- Info-bar indicators ---
        "LLM_UI_STYLE_INFO_YOLO_ON": "#f92672",
        "LLM_UI_STYLE_INFO_YOLO_PARTIAL": "#e6db74",
        "LLM_UI_STYLE_INFO_YOLO_OFF": "#a6e22e",
        "LLM_UI_STYLE_INFO_PLAN_ON": "#66d9ef",
        "LLM_UI_STYLE_INFO_PLAN_OFF": "#a6e22e",
        # --- Markdown (Rich style strings) ---
        "LLM_UI_STYLE_MARKDOWN_LINK": "bold #66d9ef underline",
        "LLM_UI_STYLE_MARKDOWN_LINK_URL": "italic #66d9ef underline",
        "LLM_UI_STYLE_MARKDOWN_H1": "bold #f92672",
        "LLM_UI_STYLE_MARKDOWN_CODE": "bold #e6db74",
        # --- CLI semantic colors (Rich color names/hex) ---
        "CLI_COLOR_WARNING": "#e6db74",
        "CLI_COLOR_ERROR": "#f92672",
        "CLI_COLOR_SUCCESS": "#a6e22e",
        "CLI_COLOR_HIGHLIGHT": "#e6db74",
        "CLI_COLOR_INFO": "#66d9ef",
        "CLI_COLOR_TODO_PROJECT": "#e6db74",
        "CLI_COLOR_TODO_CONTEXT": "#66d9ef",
        "CLI_COLOR_TODO_KEYVAL": "#ae81ff",
        # Note: LLM_UI_STYLE_BOTTOM_TOOLBAR and every CLI_STYLE_* knob are
        # deliberately omitted — they inherit their `dark` values via the merge.
    },
)
