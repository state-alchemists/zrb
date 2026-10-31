# tool_registry · L0

One-line: Shared tool registry structures used by tools and subagents.

- Layer: L0
- Purpose: Map tool names to callables and factories; resolve names.
- Public entry points: `src/zrb/llm/tool_registry.py`
- Depends on: —
- Used by: common_tools, subagent, tool resolution
- Key ADRs: ADR-0090
- Tests: `test/llm/test_common_tools.py`
