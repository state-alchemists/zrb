🔖 [Documentation Home](../README.md) > [Contributing](./) > Coding Conventions

# Coding Conventions

Zrb reads as one person's code. The same verb, the same error style, the same place for the same job, everywhere. This page is the rule book behind that, with the test or ADR that owns each rule. Read it before adding code; the enforced rule list is [Framework Conventions](framework-conventions.md) (R1–R13), and the pattern lookup is [Which pattern do I reach for?](which-pattern.md).

## The shape of the code

Before writing, read the module you are changing, the test that exercises it, and the architecture page that explains it. Then make the new code indistinguishable from its neighbours: same naming, same error handling, same layering, same test layout. Extend an existing module before inventing a new one, and add a module only when it answers a question the package does not already answer.

- **High cohesion.** One module, class or function has one reason to change. A file that needs "and" in its description is usually two files.
- **Low coupling.** A unit knows as little about its neighbours as its job allows. Pass data in, return results out, and reach another object only through a public property or method — never a `_` name (`test/architecture/test_boundaries.py::test_no_part_reaches_another_objects_private_state`).
- **Depend downward, once.** A lower layer never imports a higher one, and a package never imports its sibling back. Shared pieces move to the lower package; an annotation-only need goes behind `TYPE_CHECKING`. The graph is guarded by `test/architecture/test_llm_layering_ratchet.py`, `test/architecture/test_circular_import_allowlist.py` and `test/architecture/test_seam_module_imports.py`.
- **Compose, don't inherit.** Single inheritance is for a genuine is-a (`BaseTask`, `BaseUI`); behavior that reads a host's state is a part the host holds, and behavior that reads only state it sets itself is a `Mixin`. The full rule is [Which pattern → Mixin vs. part](which-pattern.md#the-one-hard-call-mixin-vs-part).

### SOLID in this tree

| Principle | What it means here |
| --- | --- |
| **S**ingle responsibility | One question per module, one reason per class. `task/base/execution.py` runs a task; `task/base/lifecycle.py` starts and finishes it; a file named "manager" manages one collection. |
| **O**pen/closed | Add behavior through an existing seam — an ordered collection (`append_X`/`add_X`), a hook, a factory, a registered `Any*` implementation — rather than a new branch in a chain of `if`. A new family is a registry, a manager and a `CFG` allowlist together (ADR-0090). |
| **L**iskov substitution | An implementation of `Any<Thing>` honors the contract's promises, including its error behavior. Callers program against the `Any*` type, never a concrete class ([Architecture, Philosophy & Conventions](architecture.md#interfaces-everywhere-the-any-pattern)). |
| **I**nterface segregation | Many small role contracts beat one fat one. `AnyUI` is an aggregate of five accessors (`ui.display`, `ui.input`, `ui.picker`, `ui.session`, `ui.tools`), each with its own `any_ui_<role>.py`, so a backend implements only what it replaces. |
| **D**ependency inversion | Depend on `Any*` contracts and the L0 facades (`zrb.llm.contracts.shared.agent_runner`), not on the engine or a concrete implementation. `zrb.llm` obeys the layering ladder in ADR-0120. |

## Public API

`zrb.__all__`, the public members of every exported class, and every `__init__` parameter zrb itself defines are the public API. `test/test_public_api_contract.py` pins all three against `test/public_api_snapshot.json`.

- **Prefer additive.** A new optional keyword, a new `Any*` implementation or a new registry entry does not break a caller; renaming, reordering or removing an exported name does.
- **A necessary break is announced and deliberate.** Say it in the PR body and the changelog, then regenerate the snapshot in the same diff:

```bash
UPDATE_API_SNAPSHOT=1 pytest test/test_public_api_contract.py
```

Review the snapshot diff as carefully as the code: it is the list of every caller you are about to break.

- **A removed export** goes in `_RETIRED_EXPORTS` in `src/zrb/__init__.py`; a renamed or removed `CFG` knob keeps the old env key through `EnvField(aliases=[new, old], write_key=new)`, or goes in `RETIRED_SETTINGS` in `src/zrb/config/retired.py`. Both make zrb name the old name at startup instead of silently ignoring it.
- **Docstrings are part of the surface.** Every public member of an exported class has one, and a class that adds constructor parameters documents them in its own `__init__` (`test/test_public_api_docs.py`).

## Naming

Names follow the two patterns below, plus the fixed action vocabulary that measurement kept (ADR-0098). The vocabulary and the boolean rule are review standards; only the `-> bool` half is a ratchet.

### A/HC/LC

```
prefix? + action (A) + high context (HC) + low context? (LC)
```

| Name | Prefix | Action (A) | High context (HC) | Low context (LC) |
| --- | --- | --- | --- | --- |
| `run_agent` | | `run` | `Agent` | |
| `get_root_group` | | `get` | `Root` | `Group` |
| `create_agent_hook` | | `create` | `Agent` | `Hook` |
| `append_stream_observer` | | `append` | `Stream` | `Observer` |
| `should_render_user_markdown` | `should` | `Render` | `User` | `Markdown` |

The order carries meaning: the high context is the thing being acted on, the low context narrows it. A name that reads as a value when the function returns a boolean is the common failure; `is_yolo_enabled` reads as the question a caller asks.

### S-I-D

A name is **short**, **intuitive** and **descriptive**: `get_task_status`, `is_yolo_enabled`, `should_render_user_markdown`. Not `tmp`, `data`, `process`, `do_stuff`, or `impl2`. The reference for both patterns is [kettanaito/naming-cheatsheet](https://github.com/kettanaito/naming-cheatsheet).

- No contractions: `on_item_click`, not `on_itm_clk`.
- No duplicated context: `Task.run`, not `Task.run_task`.
- Singular for one value, plural for a collection: `task` / `tasks`.
- One casing: `snake_case` for functions and variables, `PascalCase` for classes, `_ENABLED` for switches.

Two exceptions are fixed public surface, not drift: `ctx` (the first parameter of every task a user writes) and `CFG` (the config singleton). Existing names are corrected when a file is touched for another reason; there is no rename sweep.

### One verb per meaning (ADR-0098)

| Verb | Meaning | Not |
| --- | --- | --- |
| `get_X` | return X, computing or fetching it | `fetch`, `retrieve`, `lookup` |
| `resolve_X` | evaluate a deferred attribute against a context | folding it into `get` |
| `read_X` | read from the filesystem or a stream | `load` for file contents |
| `load_X` | import or deserialize a module, config or plugin | `read` for a module |
| `create_X` | construct and return a new X | `build`, `make`, `new`, `generate` |
| `enable_X` | switch an optional feature on for a task | `setup`, `install` |
| `set_X` / `reset_X` | assign X / restore its initial value | — |
| `remove_X` | take X out of a collection | `drop`, `discard`, `prune` |
| `delete_X` | destroy X at its source | `remove` for destruction |
| `handle_X` | process an event or callback | `on_X`, `process_X` |

A function annotated `-> bool` is named as a question: `is_`, `has_`, `should_`, `can_`, `needs_`, or an `_enabled`/`_active` property suffix. `test/architecture/test_bool_naming_ratchet.py` holds the count of exceptions, and it may only go down.

`Any<Thing>` is the one naming rule a test can see: every abstract extension point is named `Any<Thing>` and lives in `any_<thing>.py` in the package that owns the concept (`test/architecture/test_boundaries.py`).

## Imports and lazy loading

Default to a module-level import. An in-function import must justify itself with a `# lazy: <reason>` comment matching one of five accepted reasons, or `test/architecture/test_lazy_import_categories.py` fails:

1. **Heavy third-party deferral** — `pydantic_ai`, `prompt_toolkit`, `mcp`, `fastapi`, `boto3`, `anthropic`, `openai`, `playwright`, and the other extras-marked packages.
2. **Transitively heavy via internal** — a `zrb.*` module that eagerly imports a heavy package inherits the rule; hoisting silently restores the slow load.
3. **Circular import** — name the cycle: `# lazy: circular — tool → ui → llm_task → here`. A *new* one is a design smell: the module is usually in the wrong layer (ADR-0088), and the allowlist in `test/architecture/test_circular_import_allowlist.py` may only shrink.
4. **Test patch seam** — tests patch at the source path and rely on the patch taking effect inside a consumer; hoisting binds the name at consumer-load time and bypasses the mock. Tag: `# lazy: tests patch <path>; hoisting bypasses the mock`.
5. **Platform-only module** — the module does not exist on every supported platform (`msvcrt`, `fcntl`, `termios`). Tag the platform and what the others would pay.

Two more rules that keep startup cheap: an annotation-only name goes behind `if TYPE_CHECKING:` (`test/architecture/test_typing_only_names_are_not_evaluated.py`), and a rarely used tool sets `defer_loading=True` in `zrb/llm/common_tools.py` so the model sees its name without paying for its schema. Measure before deciding a module should be lazy: `python -X importtime -c "import zrb" 2>importtime.log`, and read the **self** column, not the cumulative one.

`flake8 src/zrb --select=F` fails on an unused or duplicate import. `# noqa: F401` belongs only on an import that exists as a test-patch attribute on the module itself; verify the patch targets working code before keeping it.

## Layout and dependencies

- **No path stutter.** `X/manager/manager.py` is `X/manager.py`; siblings become `X/manager_<aspect>.py`. The `X/X.py` paths are not this rule — `task/task.py`, `group/group.py`, `config/config.py` are `<package>/<eponymous-type>.py`, and flattening one would collide with its own package.
- **An `__init__.py` is optional.** See [Code Map → An `__init__.py` is optional](code-map.md#an-__init__py-is-optional) for when it earns its place.
- **The structure is boring on purpose.** A module answers one question, its name says which, and it sits where a reader would look first. A clever new folder is a cost every later reader pays.
- **No cycles.** A `# lazy: circular` is a comment over a misplaced edge, not a solution. If a lower module needs a higher one, move the shared piece down or invert the dependency through a contract. The three guards are listed under [The shape of the code](#the-shape-of-the-code).
- **Registration is part of the change.** A new builtin task and a new tool each have a second step that no import error reveals; see [Code Map → Registration steps](code-map.md#registration-steps-that-fail-silently-without-a-test).

## Code in the small

- **Aim for under ~30 lines per function** and put a helper below its caller. This is a target for new code, not an invariant: `test/architecture/test_complexity_ratchet.py` pins mccabe and radon at 14, and a function inflated by a nested handler may carry `# noqa: C901` with a one-line reason (it must have a nested `def` and a radon score ≤ 4).
- **Never cross a `_` name on another object.** Add the public accessor instead; this holds in tests too (`test/architecture/test_private_test_access_ratchet.py`). On a class users subclass, store an owner-only part as `self._base_<aspect>` so a subclass's own attribute cannot silently overwrite it.
- **Error handling.** An error the *model* must recover from carries `[SYSTEM SUGGESTION]` with the next action (ADR-0057); an error the *user* must fix names the setting, the bad value and the accepted values; no bare `Exception`, and no constant message under 40 characters (R10).
- **Cancellation is not an error.** Catch `(asyncio.CancelledError, KeyboardInterrupt, GeneratorExit)` separately, clean up, and re-raise ([Architecture, Philosophy & Conventions](architecture.md#handling-asynchronous-cancellation)).
- **Task constructors** spell out only the keywords they add and take the parent's as `**kwargs: Unpack[BaseTaskParams]` (`task/base/params.py`). A subclass that accepts fewer keywords forwards a narrower `TypedDict` and calls the `reject_*_params` guard; a shadowed default is `kwargs.setdefault(...)` plus an entry in `test/architecture/test_constructor_surface.py`.
- **Config knobs.** A switch is `<NAMESPACE>_ENABLED` when it is the master switch of a namespace, verb-first (`ENABLE_`/`SHOW_`/`SEARCH_`/`ALLOW_`) when standalone (R13). A new duration is seconds, `float`, and says so in its doc; a released knob is not re-scaled. No `CFG.X` read at import time: wrap it in a callable (`test/architecture/test_deferred_config_reads.py`). A renamed or removed setting keeps its old key or goes in `RETIRED_SETTINGS`.
- **Every public docstring is documentation a user reads.** Keep it true when you change the signature.

## Tests

Tests are part of the change, not a follow-up. They drive the public API, they say what the code must keep doing, and they are what the next reader trusts when the docstring is thin.

- **Public API only.** Never access or assert on a `_private` member. If internal behavior is hard to test publicly, expose a public hook or property. Mocking a public dependency is fine; mocking `_private_helper` is not (`test/architecture/test_private_test_access_ratchet.py`).
- **Arrange-Act-Assert**, pytest fixtures, and `unittest.mock.patch` for external dependencies. The usual seam for a private helper is the public entry point plus the boundary its effect crosses.
- **Naming and size.** A test sits in the mirrored path under `test/`; no `_advanced`/`_extra`/`_coverage` suffix; a file over 500 lines splits by feature group; two same-basename test files need an empty `__init__.py` in their directory ([Code Map → Test tree](code-map.md#test-tree); `test/architecture/test_test_file_size_ratchet.py`).
- **The gate.** `zrb-test.sh` runs `flake8 src/zrb --select=F`, `pyright src/zrb` (`standard`, plus the `strict` packages in `pyrightconfig.json`) and the suite with ≥95% coverage. Use `./zrb-test.sh ratchet` for the fast architecture loop.
- **Type checking.** The `strict` list in `pyrightconfig.json` only grows. Fix the root of an inference failure rather than annotating every site that inherits it.
- **Coverage is a floor, not a target.** `.coveragerc` excludes `zrb_init.py`, `__main__.py`, `any_*.py` and every `__init__.py`; write the test for the branch the change introduced instead of one that exists to raise a percentage.
- **Process-wide state leaks across xdist workers.** Read [Maintainer Guide → Process-wide state](maintainer-guide.md#process-wide-state-and-pytest-xdist) before mutating anything global, `ContextVar`s included.

## Documentation does not lag

A change updates every page, example or diagram it invalidates in the same pull request. A moved file, a renamed symbol, a changed default or a new knob with no row is a bug the doc guards catch or the review does.

- **Examples are code.** If a sample changes behavior, update `examples/` and the page that shows it; a template placeholder must reach `Tpl(...)` or `ctx.render(...)` to render (`test/architecture/test_doc_tpl_placeholders.py`).
- **The guards.** `test/architecture/test_doc_code_references.py` resolves every backticked `src/...` path and every relative link in a live doc; `test/architecture/test_doc_imports.py` imports every `zrb` name a python fence shows; `test/architecture/test_architecture_docs.py` and `test/architecture/test_architecture_doc_symbols.py` hold the architecture pages' shape and truth; `test/architecture/test_doc_indices.py` keeps every ADR and changelog file listed in its index; `test/architecture/test_recipes_run.py` runs the recipes.
- **Prose is one line per paragraph**, with no fixed-width wrapping; fenced blocks, tables, headings and hard breaks stay as written. `docs/` follows this so a one-word edit is a one-line diff ([Maintainer Guide → Writing Docs](maintainer-guide.md#writing-docs)).
- **A decision gets an ADR** when it is non-trivial, consequential and persistent, and the record that owns a changed decision is rewritten rather than superseded ([ADR index](../adr/README.md)).

---

🔖 [Documentation Home](../README.md) > [Contributing](./) > Coding Conventions
