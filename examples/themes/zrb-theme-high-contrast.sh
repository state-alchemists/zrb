#!/usr/bin/env bash
# zrb-theme-high-contrast.sh — High-contrast theme for zrb llm chat
#
# Source this file in your shell rc to apply the high-contrast theme:
#   source docs/examples/themes/zrb-theme-high-contrast.sh
#
# Or call the function directly:
#   zrb_theme_high_contrast
#
# Uses pure black/white and bright ANSI colors for maximum readability.
# Suitable for projectors, low-quality displays, or users with visual
# impairments.

zrb_theme_high_contrast() {
  # --- Frame & bars ---
  export ZRB_LLM_UI_STYLE_TITLE_BAR="#ffffff"
  export ZRB_LLM_UI_STYLE_INFO_BAR="#ffffff"
  export ZRB_LLM_UI_STYLE_FRAME="#ffffff"
  export ZRB_LLM_UI_STYLE_FRAME_LABEL="#ffff00"
  export ZRB_LLM_UI_STYLE_INPUT_FRAME="#ffffff"
  export ZRB_LLM_UI_STYLE_BOTTOM_TOOLBAR="noinherit"

  # --- Status & indicators ---
  export ZRB_LLM_UI_STYLE_STATUS="ansiwhite bold"
  export ZRB_LLM_UI_STYLE_THINKING="ansigreen bold"
  export ZRB_LLM_UI_STYLE_CONFIRMATION="ansiyellow bold"
  export ZRB_LLM_UI_STYLE_FAINT="#aaaaaa"

  # --- Text areas ---
  export ZRB_LLM_UI_STYLE_OUTPUT_FIELD="#ffffff bold"
  export ZRB_LLM_UI_STYLE_INPUT_FIELD="#ffffff bold"
  export ZRB_LLM_UI_STYLE_TEXT="#ffffff"

  # --- Choice widget (AskUserQuestion panel) ---
  export ZRB_LLM_UI_STYLE_CHOICE_BG="#000000"
  export ZRB_LLM_UI_STYLE_CHOICE_SELECTED_BG="#ffffff"

  # --- Mode badge (Shift+Tab cycle indicator) ---
  export ZRB_LLM_UI_STYLE_MODE_NORMAL="fg:ansigreen bold"
  export ZRB_LLM_UI_STYLE_MODE_ACCEPT_EDITS="fg:ansiyellow bold"
  export ZRB_LLM_UI_STYLE_MODE_PLAN="fg:ansiblue bold"
  export ZRB_LLM_UI_STYLE_MODE_YOLO="fg:ansired bold"
  export ZRB_LLM_UI_STYLE_MODE_CUSTOM="fg:ansiyellow bold"

  # --- Info-bar indicators ---
  export ZRB_LLM_UI_STYLE_INFO_YOLO_ON="ansired bold"
  export ZRB_LLM_UI_STYLE_INFO_YOLO_PARTIAL="ansiyellow bold"
  export ZRB_LLM_UI_STYLE_INFO_YOLO_OFF="ansigreen bold"
  export ZRB_LLM_UI_STYLE_INFO_PLAN_ON="ansiblue bold"
  export ZRB_LLM_UI_STYLE_INFO_PLAN_OFF="ansigreen bold"
}

# Auto-apply if sourced (not just for function definition)
if [[ "${BASH_SOURCE[0]}" != "${0}" ]]; then
  zrb_theme_high_contrast
fi
