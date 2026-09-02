🔖 [Documentation Home](../../README.md) > [Advanced Topics](./) > Framework Conventions

# Framework Conventions (R1–R12)

These are the rules a zrb component must follow to be predictable. Each is enforced by a test in `test/architecture/`; the table names which. Cite the rule number in review.

| # | Rule | Enforced by |
| --- | --- | --- |
| **R1** | Assigning an unknown `CFG.UPPERCASE` name raises `AttributeError` naming the closest real knob. | Phase 1 |
| **R2** | Assigning a value `CFG` cannot cast back raises `ValueError` at the assignment, not at the next read. | Phase 1 |
| **R3** | No `CFG.X` read happens at import time. A config value consumed by a component defined at import time is wrapped in a callable. | Phase 2 ratchet |
| **R4** | A failure loading `zrb_init.py` prints the file, line and exception type, and exits non-zero. Partial config is never silently accepted. | Phase 2 |
| **R5** | **Ordered** collections (prompts, tools, policies, formatters, processors) expose exactly `append_X`, `prepend_X`, `set_X`, `remove_X`. No `add_X`. | Phase 3 ratchet |
| **R6** | **Name-keyed** collections (skills, agents, hooks, UIs) expose exactly `add_X`, `set_X`, `remove_X(name)`, `get_X(name)`, `get_Xs()`. | Phase 3 ratchet |
| **R7** | A concept is reachable by exactly one name. No `set_history_manager()` *and* a settable `history_manager` property. No `search_dirs` property *and* `get_search_directories()`. | Phase 3 ratchet |
| **R8** | Every component a user may replace is a settable property on its host, typed as the component's `Any*` ABC or concrete class. | Phase 4 ratchet |
| **R9** | Every abstract extension point is named `Any<Thing>` and lives in `any_<thing>.py` in the package that owns the concept. | Phase 8, Phase 9 |
| **R10** | An error the *LLM* must recover from carries `[SYSTEM SUGGESTION]` (ADR-0057). An error the *user* must fix names the setting, the bad value and the accepted values. Never bare `Exception`. | Phase 9 ratchet |
| **R11** | Sibling classes in one package use one naming convention. Two conventions for the same role is a bug. | Phase 9 |
| **R12** | Every registry has exactly one canonical instance, module-level, exported from `zrb/__init__.py`. No private second registry for the same family. | Phase 7 |

See also: [Which pattern do I reach for?](which-pattern.md) — a lookup table for picking the right rule/pattern when adding new code.

---

🔖 [Documentation Home](../../README.md) > [Advanced Topics](./) > Framework Conventions
