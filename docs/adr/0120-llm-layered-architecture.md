🔖 [Documentation Home](../README.md) > [Architecture Decision Records](README.md)

# ADR-0120 — `zrb.llm` is five directories, and the directory is the layer

- **Status:** Accepted
- **Date:** October 31, 2026, rewritten November 19, 2026 for 4.0

## Context

The rule has not changed since this record was first written: a lower layer does not import a higher one, and behaviour a lower layer needs is reached through a contract it may name rather than through the package that implements it. The facades below still carry it.

What was wrong was how the rule was *measured*. A module's layer came from a table — `_UNITS_BY_LAYER` — plus a glob that granted L0 to any file called `any_*.py`. A reader could not tell from a path why a file at L4 was importable from L1, and an agent copying an example could not tell either: the answer lived in the test tree. The glob was worse than the table, because it looked like a naming convention and behaved like a rank — "contracts live here" read as "this file may be imported from anywhere".

The tree also kept twenty upward edges and two same-layer cycles in an allowlist it could never empty, because the code genuinely had them: `task/chat/running.py` imported `ui/assembly.py`, `tool/delegate/runner.py` built the buffered UI, `prompt/` and `tool/` imported each other, `subagent/` and `task/` imported each other.

## Decision

**The five directories under `llm/` are the five layers**, in order: `contracts/` L0, `capabilities/` L1, `engine/` L2, `orchestration/` L3, `presentation/` L4. A module's layer is its first path segment, so a path states its own rank and nothing has to be looked up. The table and the glob are both gone; `llm/` holds the five directories and nothing else, and a guard fails if a sixth appears.

**Two exceptions, written as a prefix.** `presentation/ui/fallback/` and `presentation/ui/buffered/` score L0 inside an L4 package. The first is the plain terminal UI a headless run needs; the second is the buffer a delegation builds per sub-agent, which `capabilities/tool/delegate/runner.py` constructs and `orchestration/subagent/live_session.py` speaks to. Neither may drag the UI package that answers it. The `AnyUI*` protocols these floors build with stay in `presentation/ui/`, beside their implementers: sent down to `contracts/` they would import `presentation/` back at it, which is the edge the floors exist to avoid.

**One file is exempt: `engine/agent/types.py`.** It re-exports the pydantic-ai types the run loop hands around by the framework's own names, so it is a facade rather than a module of its own, and it scores L0 wherever it is imported from.

**Shared behaviour is reached through L0 contracts and registries**, not through the package that implements it:

- Agent build/run: `AnyAgentRunner` (`any_agent.py`, `any_agent_result.py`, `any_agent_runner.py`) and the facade `contracts/shared/agent_runner.py`, which names those protocols for the type checker only; the engine registers its adapter when `engine/agent/__init__.py` loads.
- Delegation: `AnySubAgentManager`/`AnySubAgentDefinition` and `AnyLiveSessionRegistry`/`AnyLiveSubAgentSession`, reached through `contracts/shared/delegation_api.py`; `orchestration/subagent/` registers its singletons at import.
- A UI backend: `AnyUI` and its five role contracts in `presentation/ui/any_ui.py`, reached as accessors rather than inherited.

**Everything a lower layer must name lives where its path says.** `contracts/shared/` holds the vocabulary, the seams and the leaf helpers; `contracts/ui/` and `contracts/config/` hold the UI roles and the configuration; `contracts/memory/` and `contracts/util/` hold the store and the streaming helpers.

**The move is the announced break of 4.0, and there is no shim.** `zrb.llm.ui`, `zrb.llm.task`, `zrb.llm.tool`, `zrb.llm.camera` and the rest no longer resolve. A compatibility package would have to import the package above it, so it would restore the very upward edge the move removes, and it would leave the old spelling standing in the tree as the example the next contributor copies.

## Consequences

A path tells a reader and an agent which layer it is in, so the rule travels with the code instead of with a table in the test tree. Both ratchet allowlists — upward edges and same-layer cycles — are empty and may only stay that way: the cycles that had to exist were each replaced by a contract or a seam, so no `# lazy: circular` workaround remains for them.

The cost is a breaking change to import paths, paid once at 4.0 and written up in the changelog and the upgrading guide. Downstream code that names any moved package has to be updated; the guide names the new path for each old one.

## Alternatives rejected

- **Keep the table and let it grow.** It was already the answer to "what layer is this?", living in a file no reader of the module sees. A table a guard reads is a rule only the guard knows.
- **Grant L0 by filename (`any_*.py`) forever.** The name of a file decided its rank, so what read as a convention was a privilege — and the privilege was invisible from the path.
- **One commit for the whole move.** Seven directories at once would have made the diff unreviewable and a failure un-attributable. The guards were built to read a half-moved tree precisely so each directory could land alone, with its own evidence.
- **A shim for each old package.** Cheaper for the first upgrade and more expensive for every one after it: the old path keeps working, keeps appearing in examples, and keeps teaching the layout that was replaced.
- **Renumber the duplicate ADR-0120 while rewriting this one.** Two records share the number; which of them moves is a naming decision that belongs to the maintainer, and this rewrite does not need it settled.

## Where it lives

- `test/architecture/llm_layers.py` — the five layers, the two floors and the one exemption, as the guards read them.
- `test/architecture/test_llm_layer_rules.py` — the rules about a path, including the guard that `llm/` holds only the five directories.
- `test/architecture/test_llm_layering_ratchet.py` — those rules applied to every import in the tree: upward edges and same-layer cycles, both allowlists empty.
- `test/architecture/test_circular_import_allowlist.py` — the deferred-import allowlist, which the move emptied.
- `test/architecture/test_boundaries.py` — the `Any*` protocol naming rule, which still counts every contract.
- `src/zrb/llm/contracts/shared/agent_runner.py`, `delegation_api.py` — the two seams a higher package registers itself into.
