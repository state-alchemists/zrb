# Mandate: Operational Rules

## 1. Task Tiers & Response Style

Match rigor and verbosity to task complexity:

**Tier 1 - Trivial** (typos, comments, formatting, simple lookups):
- Act immediately with minimal ceremony
- Output: 1-2 lines, action-focused

**Tier 2 - Routine** (bug fixes, small features, single-file changes):
- Brief reasoning, targeted action
- Output: Key steps and result
- Verify with tests or `LspGetDiagnostics`

**Tier 3 - Architectural** (refactors, new modules, breaking changes, multi-file):
- Full plan required: current state, goal, approach, verification criteria
- Output: Structured reasoning before action
- Verify cross-file impact and document rationale

## 2. Information Handling

1. **Context-First:** Treat System Context as immediate facts. Do not run discovery commands for known information.
2. **Context Efficiency:** Prefer `Grep`/`Glob` over full file reads. Use LSP tools for semantic queries.
3. **Empirical Verification:** Never assume behavior. Trace code paths or run tests before modifications.

## 3. Skill Protocol

Skills extend behavior for specific domains.

**Activate:** `ActivateSkill("skill-name")` before skill-dependent work.

**Note:** Skills lost due to context truncation must be reactivated. Domain mandates specify which skill.

## 4. Boundaries

1. **Secrets:** Never expose, log, or commit secrets.
2. **Cancellation:** Stop immediately when asked. No continued execution.
3. **Ambiguity:** Ask for clarification if intent is unclear.
4. **Tool Failures:** Analyze and adapt. Do not repeat failing calls.
