# snapshot · L1

One-line: Working-tree snapshots (store/list/restore) for before/after diffs.

- Layer: L1
- Purpose: Save/restore file trees; list snapshots per repo.
- Public entry points: `src/zrb/llm/snapshot/*`
- Depends on: git utils
- Used by: tool/journal, runner web routes
- Key ADRs: ADR-0101
- Tests: `test/llm/snapshot/*`
