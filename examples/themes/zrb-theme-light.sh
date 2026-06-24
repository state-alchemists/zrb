#!/usr/bin/env bash
# zrb-theme-light.sh — Light terminal theme for zrb llm chat
#
# Source this file in your shell rc to apply the light theme:
#   source docs/examples/themes/zrb-theme-light.sh
#
# Or call the function directly:
#   zrb_theme_light
#
# Designed for terminals with a light/white background. Dark text on
# light backgrounds, with muted borders and subtle highlights.

zrb_theme_light() {
  # --- Frame & bars ---
  export ZRB_LLM_UI_STYLE_TITLE_BAR="#000000"
  export ZRB_LLM_UI_STYLE_INFO_BAR="#000000"
  export ZRB_LLM_UI_STYLE_FRAME="#bbbbbb"
  export ZRB_LLM_UI_STYLE_FRAME_LABEL="#996600"
  export ZRB_LLM_UI_STYLE_INPUT_FRAME="#bbbbbb"
  export ZRB_LLM_UI_STYLE_BOTTOM_TOOLBAR="noinherit"

  # --- Status & indicators ---
  export ZRB_LLM_UI_STYLE_STATUS="ansiblack"
  export ZRB_LLM_UI_STYLE_THINKING="ansigreen"
  export ZRB_LLM_UI_STYLE_CONFIRMATION="ansiyellow"
  export ZRB_LLM_UI_STYLE_FAINT="#999999"

  # --- Text areas ---
  export ZRB_LLM_UI_STYLE_OUTPUT_FIELD="#222222"
  export ZRB_LLM_UI_STYLE_INPUT_FIELD="#222222"
  export ZRB_LLM_UI_STYLE_TEXT="#222222"

  # --- Choice widget (AskUserQuestion panel) ---
  export ZRB_LLM_UI_STYLE_CHOICE_BG="#f5f5f5"
  export ZRB_LLM_UI_STYLE_CHOICE_SELECTED_BG="#cce5ff"

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
  zrb_theme_light
fi
