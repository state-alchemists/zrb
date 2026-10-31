# config · L0

One-line: LLM-specific configuration (model resolver knobs, limiter settings).

- Layer: L0
- Purpose: Hold LLM config mixins and helpers used across LLM subsystems.
- Public entry points: `src/zrb/llm/config/*`
- Depends on: global config, env
- Used by: agent/run, prompt, tool, permission, history_manager
- Key ADRs: ADR-0021..0027, ADR-0120
- Tests: `test/llm/config/*`
