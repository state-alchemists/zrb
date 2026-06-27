#!/usr/bin/env bash
# zrb-theme-dark.sh — Dark terminal theme for zrb llm chat
#
# Source this file in your shell rc to apply the dark theme:
#   source docs/examples/themes/zrb-theme-dark.sh
#
# Or call the function directly:
#   zrb_theme_dark
#
# This is the default theme — these values match the built-in defaults.

zrb_theme_dark() {
  # --- Frame & bars ---
  export ZRB_LLM_UI_STYLE_TITLE_BAR="#ffffff"
  export ZRB_LLM_UI_STYLE_INFO_BAR="#ffffff"
  export ZRB_LLM_UI_STYLE_FRAME="#888888"
  export ZRB_LLM_UI_STYLE_FRAME_LABEL="#ffff00"
  export ZRB_LLM_UI_STYLE_INPUT_FRAME="#888888"
  export ZRB_LLM_UI_STYLE_BOTTOM_TOOLBAR="noinherit"

  # --- Status & indicators ---
  export ZRB_LLM_UI_STYLE_STATUS="ansiwhite"
  export ZRB_LLM_UI_STYLE_THINKING="ansigreen"
  export ZRB_LLM_UI_STYLE_CONFIRMATION="ansiyellow"
  export ZRB_LLM_UI_STYLE_FAINT="#888888"

  # --- Text areas ---
  export ZRB_LLM_UI_STYLE_OUTPUT_FIELD="#eeeeee"
  export ZRB_LLM_UI_STYLE_INPUT_FIELD="#eeeeee"
  export ZRB_LLM_UI_STYLE_TEXT="#eeeeee"

  # --- Choice widget (AskUserQuestion panel) ---
  export ZRB_LLM_UI_STYLE_CHOICE_BG="#1f1f1f"
  export ZRB_LLM_UI_STYLE_CHOICE_SELECTED_BG="#264f78"

  # --- Mode badge (Shift+Tab cycle indicator) ---
  export ZRB_LLM_UI_STYLE_MODE_NORMAL="fg:ansigreen"
  export ZRB_LLM_UI_STYLE_MODE_ACCEPT_EDITS="fg:ansiyellow bold"
  export ZRB_LLM_UI_STYLE_MODE_PLAN="fg:ansiblue bold"
  export ZRB_LLM_UI_STYLE_MODE_YOLO="fg:ansired bold"
  export ZRB_LLM_UI_STYLE_MODE_CUSTOM="fg:ansiyellow bold"

  # --- Info-bar indicators ---
  export ZRB_LLM_UI_STYLE_INFO_YOLO_ON="ansired"
  export ZRB_LLM_UI_STYLE_INFO_YOLO_PARTIAL="ansiyellow"
  export ZRB_LLM_UI_STYLE_INFO_YOLO_OFF="ansigreen"
  export ZRB_LLM_UI_STYLE_INFO_PLAN_ON="ansiblue"
  export ZRB_LLM_UI_STYLE_INFO_PLAN_OFF="ansigreen"
}

# Auto-apply if sourced (not just for function definition)
if [[ "${BASH_SOURCE[0]}" != "${0}" ]]; then
  zrb_theme_dark
fi
