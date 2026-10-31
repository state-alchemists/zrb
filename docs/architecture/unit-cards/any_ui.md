# any_ui · L0

One-line: The UI contract every UI must implement; outside the ui/ package.

- Layer: L0
- Purpose: Define the AnyUI ABC without importing the presentation layer.
- Public entry points: `src/zrb/llm/any_ui.py`
- Depends on: —
- Used by: ui_fallback, ui, agent/run
- Key ADRs: ADR-0088, ADR-0120
- Tests: `test/llm/ui/*`
