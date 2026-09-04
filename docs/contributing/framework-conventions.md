🔖 [Documentation Home](../../README.md) > [Contributing](./) > Framework Conventions

# Framework Conventions (R1–R12)

These are the rules a zrb component must follow to be predictable. Each is enforced by a test in `test/architecture/`; the table names which. Cite the rule number in review.

| # | Rule | Enforced by (paths relative to `test/`) |
| --- | --- | --- |
| **R1** | Assigning an unknown `CFG.UPPERCASE` name raises `AttributeError` naming the closest real knob. | `config/test_config_assignment_safety.py::test_assigning_an_unknown_uppercase_knob_raises_and_suggests` |
| **R2** | Assigning a value `CFG` cannot cast back raises `ValueError` at the assignment, not at the next read. | `config/test_config_assignment_safety.py::test_assigning_an_uncastable_value_raises_at_the_assignment` |
| **R3** | No `CFG.X` read happens at import time. A config value consumed by a component defined at import time is wrapped in a callable. | `architecture/test_deferred_config_reads.py` |
| **R4** | A failure loading `zrb_init.py` prints the file, line and exception type to stderr, and startup continues — the error is never swallowed, but a broken init source does not stop the user from running (and fixing) anything. | `test_main.py::test_a_broken_init_script_reports_file_line_and_type_but_still_runs` |
| **R5** | **Ordered** collections (prompts, tools, policies, formatters, processors, UIs) expose exactly `append_X`, `prepend_X`, `set_X`, `remove_X`. No `add_X`. | `architecture/test_mutation_surface.py::test_every_ordered_collection_has_the_full_verb_set` |
| **R6** | **Name-keyed** collections (skills, agents) and the **event-keyed** hook collection expose exactly `add_X`, `set_X` (wholesale), `remove_X(key)`. No `append_X`. A query pair (`get_X(key)`/`get_Xs()`) is expected too, using a disambiguated stem where the plain one would collide with another concept the same host exposes (`SubAgentManager.get_agent_definition` — `create_agent` already returns a runtime agent, so `get_agent` would be ambiguous) or has no natural per-key lookup (hooks are keyed by event, not name — there is no `get_hook(name)`). | `architecture/test_mutation_surface.py::test_every_keyed_collection_has_the_minimum_verb_set` |
| **R7** | A concept is reachable by exactly one name. No `set_history_manager()` *and* a settable `history_manager` property. No `search_dirs` property *and* `get_search_directories()`. | `architecture/test_mutation_surface.py::test_no_concept_is_reachable_by_two_names` |
| **R8** | Every component a user may replace is a settable property on its host, typed as the component's `Any*` ABC or concrete class. | `architecture/test_mutation_surface.py::test_every_declared_slot_is_settable_and_typed` |
| **R9** | Every abstract extension point is named `Any<Thing>` and lives in `any_<thing>.py` in the package that owns the concept. | `architecture/test_boundaries.py::test_every_extension_point_is_named_any_thing_in_any_thing_py` |
| **R10** | An error the *LLM* must recover from carries `[SYSTEM SUGGESTION]` (ADR-0057). An error the *user* must fix names the setting, the bad value and the accepted values. Never bare `Exception`. | `architecture/test_boundaries.py::test_no_bare_exception_is_raised`, `::test_no_error_message_is_shorter_than_forty_characters` |
| **R11** | Sibling classes in one package use one naming convention. Two conventions for the same role is a bug. | `architecture/test_boundaries.py::test_config_mixins_share_one_naming_convention` |
| **R12** | Every registry has exactly one canonical instance, module-level, exported from `zrb/__init__.py`. No private second registry for the same family. | `architecture/test_mutation_surface.py::test_there_is_exactly_one_configuration_object`, `::test_managers_expose_the_same_roster_api` |

See also: [Which pattern do I reach for?](which-pattern.md) — a lookup table for picking the right rule/pattern when adding new code.

## R7, two specific cases

- **Search directories.** Every manager that scans a filesystem (`HookManager`,
  `SkillManager`, `SubAgentManager`) exposes exactly one settable `search_dirs`
  property: reading it returns the explicit override if one was set (at
  construction or by assignment), else the computed defaults; there is no
  separate `get_search_directories()`. `SubAgentManager`'s `root_dir` — a
  *different* concept, the scan root, not a search directory — is
  `scan_root`, so it cannot be confused with `search_dirs`.
- **Component slot vs. collection.** A settable property (`history_manager`,
  `prompt_manager`), not a `set_X()` method, when the slot holds exactly one
  thing. `set_X()` is for *collections* — it means "replace the whole list"
  (ADR-0090 Part 2) — so a single-value slot never gets both. Two collections
  (`ui_factories`, `approval_channels`) already had a settable plural property
  before this rule existed; R7 keeps that property as their "replace
  wholesale" spelling rather than adding a `set_X()` that would just be a
  second name for the same thing.

---

🔖 [Documentation Home](../../README.md) > [Contributing](./) > Framework Conventions
