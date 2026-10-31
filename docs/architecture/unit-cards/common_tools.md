# common_tools · L3

One-line: Seed the shared tool and toolset surface used by the engine and subagents.

- Layer: L3
- Purpose: Register the zrb-shipped tools and factories.
- Public entry points: `src/zrb/llm/common_tools.py`
- Depends on: tool, tool_registry (L1/L0)
- Used by: subagent.manager (L3), tasks (L3)
- Key ADRs: ADR-0090, ADR-0120
- Tests: `test/llm/test_common_tools.py`
