# Handover: cognitive-load and maintainability architecture work

Branch: `refactor/cohesion-dedup-whitelabel`. Nothing below is committed. Project rules are in `AGENTS.md`: no Claude attribution lines in commits or PRs (user memory `no-claude-commit-signature`), and ask when the approach is ambiguous.

## 1. Context

The user asked for a brutal review of zrb against this goal: a pleasant, correct, high-performing framework that makes sense at first sight, is configurable and is easy to maintain.

The review scored it **66/100**. The strengths were test discipline and typing. The weaknesses were these:

- **Hub coupling.** The `llm/` subsystem is 73% of the source (73.5k of 100k lines).
- **God objects.** `BaseUI` has 140 methods, `LLMChatTask` 134, and `LLMChatTask.__init__` is 232 lines.
- **Swallowed errors.** There are 329 `except Exception` sites; the ratchet baseline for swallowed ones is 303.
- **Config sprawl.** `CFG` has 388 public attributes.
- **Contributor load.** There are about 12.5k words to read before a first change.

The user then narrowed the brief to **architecture, cognitive load and maintainability**:

- A person should be able to hold one context at a time.
- Changing one feature should not break others.
- A reader should be able to pinpoint quickly which part does what.
- ADRs, docs and architecture documents should be readable with low cognitive load.
- **Splitting out a `zrb-llm` package was rejected.** It moves the complexity and does not remove it.
- The user said to slim down the contributor load.

## 2. Evidence behind the plan

These numbers were measured on the working tree, with import counts including lazy imports.

- **`llm/` has 42 units:** 27 subpackages and 15 loose modules. Unit sizes: `ui` 14.7k lines, `tool` 11k, `agent` 5.5k, `dictation` 5.1k, `speech` 4.7k.
- **Hubs:** fan-in/fan-out are `agent` 22/19, `ui` 13/20, `tool` 5/21, `task` 7/19. The periphery is already isolated: `dictation` has fan-in 1 and `speech` 3.
- **Blast radius** (180 days, 1,148 commits):
  - The median commit touches 2 modules.
  - 32% touch 3 or more modules, 17% touch 5 or more, and 6% touch 8 or more.
  - The most co-changed pairs are `agent`↔`tool` (50), `agent`↔`ui` (48), `tool`↔`ui` (43) and `config`↔`ui` (39).
  - The branch is itself a refactor, which inflates these.
- **Cycles, first count:** 28 mutual unit pairs. 21 are cycles at module level in both directions, and 7 look acyclic only because one side is a lazy import.
- **Docs:**
  - There are 134 ADRs totalling 95.6k words (median 624, p90 1,369, longest ADR-0055 at 3,825).
  - All docs total 335k words, and architecture docs 34k.
  - Before a first change a contributor is pointed at roughly 12.5k words: `AGENTS.md` 3.1k, the maintainer guide 2.9k, the ADR README 2.1k and others.
  - `docs/architecture/change-map.md` is a good "I want to… → open this file" table (1,158 words). It misses about 20 `llm/` units: `summarizer`, `snapshot`, `lsp`, `subagent`, `task`, `tool_call`, `approval`, `util`, `message`, `tool_registry` and others.

## 3. Decision and why

Seven shapes were compared: status quo with ratchets, strict layers, vertical slices, hexagonal ports and adapters, an event bus, a package split, and module cards with manifests.

**Chosen: a layered modular monolith with enforced module cards.** That is B (layers) + G (cards), with D (ports) used only where a Protocol already exists or a real behavioural dependency needs one.

The reasons:

- **Layers break the cycles.** An import cycle is the actual cause of "change one thing, break another". A one-way import rule is simple to state and a test can enforce it.
- **Cards make it readable and keep it from drifting.** A card is a short page per unit, checked against the real imports.
- **The event bus was rejected.** It decouples well, but indirect control flow makes "what runs when I do X?" hard to answer, which is the thing being optimised.
- **Vertical slices help only where the code is already isolated.** The voice and camera features are, so there is nothing to gain there.
- **`zrb-llm` was rejected by the user.**

Intended layers (logical, not directory moves; moves break deep imports, so defer them):

| Layer | Meaning |
|---|---|
| L0 contracts | Protocols, shared types, ambient state, leaf helpers |
| L1 capabilities | Tools, hooks, permissions, prompt, skills, LSP, snapshots, approval, history |
| L2 engine | `agent`, `summarizer` |
| L3 orchestration | `task`, `subagent`, `custom_command`, `common_tools` |
| L4 presentation | `ui`, `app`, `dictation`, `speech`, `camera`, `screenshot`, `voice`, `emotion` |

A lower layer never imports a higher one. Modules that exist to be depended on count as L0 wherever they live: the `any_*.py` Protocol files and `agent/types.py`. Treating them that way cut upward unit-pairs from **30 to 13**. The first count was a classification error, not real debt.

## 4. What has been done

One file was added and nothing else was changed: **`test/architecture/test_llm_layering_ratchet.py`** (239 lines, untracked).

- Every `llm/` unit must be assigned a layer in `_UNITS_BY_LAYER`.
- **No new upward import:** 28 are allowlisted in `KNOWN_UPWARD_EDGES`. Only runtime imports count; `if TYPE_CHECKING` blocks are excluded.
- **No new same-layer cycle:** 2 are allowlisted in `KNOWN_SAME_LAYER_CYCLES` (`subagent <-> task`, `prompt <-> tool`).
- **Both allowlists are tight:** fixing an edge without deleting its line fails. This is the same pattern as `test_broad_except_ratchet.py`.

Verified:

- The 5 new tests pass, and all 744 tests in `test/architecture` pass.
- The ratchet was checked in both directions: a removed entry is reported as new, and a fake entry is reported as stale.
- flake8 `--select=F` is clean.

**Not run:** the full test suite, pyright, and coverage. The new file is a test only, so it is excluded from coverage and from pyright's `src/zrb` scope.

**Status after the latest turn:** group 1 is done (see section 5). Earlier:  `subagent` was moved to L3 and the allowlists regenerated (28 upward edges, 2 cycles, 5 tests passing). Groups 1 and 2 below were **not started**; context ran out first.

## 5. What still needs to be done

### Reduce the upward edges, in this order

1. ~~**Move pure code down (3 edges).**~~ **DONE.**
   - `tool_call/args.py` moved to `util/tool_args.py`; every importer, the test (`test/llm/util/test_tool_args.py`), `docs/llm/tool-approval.md` and the upgrading-guide row were updated.
   - `append_live_context` / `split_live_context` and their regex moved from `prompt/live_context.py` to the new `util/live_context_block.py`; importers updated and the split tests moved to `test/llm/util/test_live_context_block.py`.
   - The three allowlist lines were deleted. Ratchet is now at 25 upward edges.
   - Verified: `test/architecture`, `test/llm/{util,prompt,tool_call,agent,ui/base}`, `test/util`, `test/runner/chat` all pass (2,943 tests); `flake8 --select=F` clean. Full suite, pyright and coverage not run.
2. **Ambient lookups (5 edges): half done.**
   - ~~`current_approval_channel`~~ **DONE.** The `ContextVar` is now defined in `agent_state.py`; `approval/approval_channel.py` re-exports it, so no importer changed. Ratchet is at 24 upward edges. Verified with `test/architecture`, `test/llm/{approval,hook,agent,subagent}`, `test_agent_state.py` and `test_contextvars_index.py` (1,653 passed).
   - **`ui/multi_ui.resolve_ui` / `get_main_ui` is NOT a pure move, contrary to the first plan.** `resolve_ui` constructs `StdUI` or `MultiUI`, and `get_main_ui` does `isinstance(ui, MultiUI)`, so they need the concrete L4 classes. Callers: `agent/run/setup.py`, `task/chat/execution.py`, `task/chat/running.py`, `tool/delegate.py`, `tool/delegate_background.py`.
   - **User chose option (a)** (ambient UI factory in `agent_state`, registered by the UI layer). **Not implemented yet; investigation found a blocker to design first:**
     - `agent/run/setup.py` imports `ui.multi_ui` eagerly today, which *guarantees* `StdUI`/`MultiUI` exist whenever an agent runs. Line 76 calls `resolve_ui(...)` with `None` and relies on the `StdUI` fallback.
     - With registration, that guarantee goes. `zrb/llm/` has no `__init__.py` (namespace package), so there is no single import point that always registers the resolver. Callers of `run_agent` that may never import `zrb.llm.ui`: `tool/web.py`, `tool/code.py`, `agent/run/multimodal_describe.py`, `dictation/backend/multimodal.py`.
     - A string-based `importlib` fallback inside `agent_state` would hide the upward dependency from the ratchet. Do not do that.
   - Design choices still open: (i) register the resolver from `zrb/llm/ui/__init__.py` *and* make `agent/run/setup.py` fail loudly (with a `[SYSTEM SUGGESTION]` message, per R10) when none is registered; (ii) give the headless case its own tiny L0 fallback UI (a no-op `AnyUI`) so `None` never needs `StdUI`; (iii) keep `agent/run/setup.py -> ui/multi_ui.py` allowlisted and fix only `tool/delegate*.py`.
   - `get_main_ui` alone can be duck-typed in L0 (`getattr(ui, "main_ui", None)`, since only `MultiUI` defines `main_ui`) with no interface change, but that removes no edge until `resolve_ui` moves too.
   - Whichever is chosen: add a test that `run_agent` with no UI imported still works (run it in a subprocess that never imports `zrb.llm.ui`).

3. **Add one small `AgentRunner` Protocol in L0 (6 edges).** Register the implementation from the engine layer, the same way as for the UI.
   - Callers: `hook/creator.py`, `history_manager/conversation_naming.py`, `tool/code.py`, `tool/web.py` and `tool/file_analyze.py`.
   - `tool/file_read.py -> agent/run/multimodal_describe.py` may belong here too. Check that.
4. **Split the delegation tools from the plain tools (about 14 edges).** `tool/delegate*.py`, `subagent/building.py`, `subagent/live_session.py`, `subagent/manager.py` and `subagent/parent_message.py` build and drive agents and UIs, so they are orchestration. Reclassify or physically move them; a Protocol here would be about 1,000 lines of surface to hide a real dependency.
   - The open question is `subagent`. It builds a `LLMChatTask` (L3) and cycles with `agent`.
   - Moving it to L3 resolves the cycle, and the `agent -> subagent` lazy edge then becomes an upward one that the ratchet will flag.
   - Decide with the user.

Each fix deletes allowlist lines. Do not add a line to admit new code.

### Other planned steps, not started

5. **Module cards.** Write a README of at most about 150 words in each unit directory:
   - purpose, public entry points, layer, depends on, used by, tests, and the one ADR that matters;
   - a test checks "depends on" against the real imports;
   - generate `change-map.md` from the cards so it covers all 42 units.
6. **Docs diet.**
   - Trim `AGENTS.md` from 3,097 words to about 800.
   - Add a 5-line Rule box at the top of each ADR: the invariant, what enforces it, where it lives.
   - Split ADRs over about 1,400 words into rule and rationale.
   - Regroup the ADR index by layer.
   - Target: under about 2k words to read before a first change.
7. **Context budget.** A unit should be about 3k lines or split into carded sub-units. Start with `ui` and `tool`.
8. **An ADR for the layers**, plus a line in `AGENTS.md` and a row in the `docs/contributing/framework-conventions.md` table. The rule currently lives only in the test docstring. `test_doc_indices` and the doc-reference tests will check the additions.

### Success targets

- Mutual dependencies: 28 → 0.
- Commits touching 5 or more modules: 17% → under 8%.
- Change-map coverage of `llm/` units: about 55% → 100%.
- Words to read before a first change: about 12.5k → under 2k.

## 6. Pitfalls and conventions

- **Never run `black`, `isort` or any formatter over `src/` or `test/` as a whole.** Doing so reformatted about 37 unrelated files; they had to be reverted one by one. Format only the files you wrote, and check `git diff --stat` stays small.
- **Do not run a blanket `git checkout -- src test docs`.** The harness blocks it because it would discard all uncommitted work. Revert by explicit file list.
- Moving a module also means moving its mirrored test, updating docs that name the path, and (for a renamed public path) the upgrading-guide table.
- **Run `./zrb-test.sh ratchet`** (it runs `test/architecture`) while working.
- **ADR rules:** rewrite the owning record when a decision changes. Do not add a superseding chain.
- **Doc rules:** one line per Markdown paragraph. Prompt text under `src/zrb/llm/prompt/markdown/` is out of scope.
- **Imports:** lazy imports need a `# lazy:` reason (`test_lazy_import_categories.py`).
- **Tests:** they must not touch private members. A new test file must stay under 500 lines and follow the mirrored naming rules.
- **Behaviour changes need equivalence checks.** Summarization and history code has a recorded caution in user memory: preserve the last-N messages and tool-call pairing.
- **Caveats on the numbers:**
  - Import counts include lazy imports.
  - Co-change counts come from a refactor branch.
  - The layer assignment is a proposal. `tool_call` was moved to L1 and `subagent` left at L2 on judgment, without close reading.
- **The throwaway analysis scripts** were in the session scratchpad. The test file now contains the same logic, so the scratchpad copies can be ignored.
