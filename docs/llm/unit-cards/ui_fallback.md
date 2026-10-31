# ui_fallback · L0

One-line: Headless-safe UI construction and combination without importing the presentation layer.

- Layer: L0
- Purpose: Provide `StdUI`, `UIStateDefaultsMixin`, and `resolve_ui`/`create_combined_ui`/`get_main_ui`.
- Public entry points: `src/zrb/llm/ui_fallback/std_ui.py`, `state_defaults.py`, `resolution.py`
- Depends on: any_ui (L0)
- Used by: agent/run, task/chat, tools that normalize UIs (L2–L3–L1)
- Key ADRs: ADR-0074, ADR-0116 (UI queue and send-now), ADR-0120
- Tests: `test/llm/agent/run/test_setup_ui_fallback.py`, `test/llm/ui/test_multi_ui.py`
