# Runners & packaging

How tasks reach users, and how the project ships. See the [ADR index](README.md)
for format and tags.

---

## ADR-0026 — One task definition, multiple runners (CLI + Web)

**Status:** Accepted

**Context.** The same automation should be runnable from a terminal and a
browser without redefining it.

**Decision.** `AnyTask` is runner-agnostic. The CLI runner parses `sys.argv`,
resolves the group/task path, builds context, and calls `task.run()`. The web
runner wraps the *same* task in FastAPI routes, auto-generating input forms and
streaming output. Both share Session/SharedContext/XCom.

**Consequences.** No duplication or API-translation layer; identical logic and
ordering across surfaces; prototype on CLI, expose on web. Cost: task design
must stay transport-neutral.

**Alternatives rejected.** Separate CLI/web definitions (duplication, skew); an
RPC API over CLI tasks (loses streaming/input-binding/DAG richness); web-only
(loses shell/scripting/piping).

**Evidence.** **[DOCUMENTED]** `docs/advanced-topics/web-ui.md`,
`architecture.md` ("Dual-Mode Execution"). **[INFERRED]** `src/zrb/runner/cli.py`,
`src/zrb/runner/web_app.py` (both call the same task).

---

## ADR-0027 — FastAPI + Uvicorn for the web runner

**Status:** Accepted

**Context.** The web runner must match an async core and stream task/LLM output.

**Decision.** Use FastAPI (with Uvicorn) for the web server, imported lazily so
the CLI startup doesn't pay for it.

**Consequences.** Native async end-to-end (no sync↔async bridges), SSE/WebSocket
streaming, Pydantic request validation, minimal routing boilerplate. Cost: a
heavyweight optional dependency (deferred via lazy import).

**Alternatives rejected.** Flask (no native async; thread-based); Django
(heavyweight, ORM-centric); aiohttp (more routing boilerplate).

**Evidence.** **[DOCUMENTED]** `docs/advanced-topics/web-ui.md`, `pyproject.toml`
(`fastapi` with standard extras). **[INFERRED]** `src/zrb/runner/web_app.py`
(lazy `from fastapi import FastAPI`, lifespan), `runner/chat/sse_stream.py`.

---

## ADR-0028 — Nested CLI groups (`zrb <group> <task>`)

**Status:** Accepted

**Context.** Hundreds of tasks need navigable organization.

**Decision.** Tasks live in a tree of `Group`s under a root `Cli`. Invocation is
`zrb group subgroup task [args]` (like `git commit`). Aliases decouple display
names from Python names; snake_case auto-maps to kebab-case.

**Consequences.** Semantic, discoverable command surface that scales; groups
nest arbitrarily. Cost: deep nesting can make commands verbose.

**Alternatives rejected.** Flat namespace (unmanageable at scale);
config-driven groups (fights ADR-0001).

**Evidence.** **[DOCUMENTED]** `docs/core-concepts/cli-and-groups.md`.
**[INFERRED]** `src/zrb/group/group.py`, `src/zrb/runner/cli.py`.

---

## ADR-0029 — Battery-included builtin tasks, toggleable

**Status:** Accepted

**Context.** Common utilities (git, base64, uuid, http, todo, project scaffolds)
shouldn't be rebuilt by every user, but a white-labeled distro may want a clean
namespace.

**Decision.** Ship builtin task groups under `src/zrb/builtin/`, registered to
the root CLI behind a `CFG.LOAD_BUILTIN` toggle (default on).

**Consequences.** Useful on day one and discoverable via `zrb`; deployments can
disable builtins to reduce clutter. Cost: builtins are part of the core package
(not a separate install).

**Alternatives rejected.** No builtins / separate `zrb-extras` (install
friction); all-optional plugins (poor discoverability); always-on (inflexible
for white-labeling).

**Evidence.** **[DOCUMENTED]** `docs/task-types/builtin-helpers.md`.
**[INFERRED]** `src/zrb/builtin/group.py` (`_maybe_add_group` checks
`LOAD_BUILTIN`), `config/mixins/foundation.py` (`DEFAULT_LOAD_BUILTIN`).

---

## ADR-0030 — Plugin/skill/agent discovery from directories

**Status:** Accepted

**Context.** LLM capabilities (skills, sub-agents) must be extensible per project
and shareable, ideally interoperating with Claude's config layout.

**Decision.** Discover skills (`SKILL.md`/`SKILL.py`) and agents (`*.agent.md`)
from configurable directories — project-local, home (`~/.claude/`, `~/.zrb/`),
plugin dirs (`ZRB_LLM_PLUGIN_DIRS`), and the builtin `src/zrb/llm_plugin/` — with
project overriding home overriding builtin. Dir names are configurable
(`ZRB_LLM_CONFIG_DIR_NAMES`, default `.claude:.zrb`).

**Consequences.** Decentralized, no central registry; one skill library can serve
both Claude Code and zrb. Cost: discovery precedence is a non-trivial mental
model.

**Alternatives rejected.** Hardcoded skill set (inflexible); pip-installed plugin
packages (friction, weak discoverability, poor offline story); single global
registry (governance bottleneck).

**Evidence.** **[DOCUMENTED]** `docs/advanced-topics/llm-integration.md`,
`claude-compatibility.md`, `AGENTS.md` (`llm_plugin/` layout). **[INFERRED]**
`src/zrb/config/mixins/llm_search.py`, `src/zrb/llm_plugin/`.

---

## ADR-0031 — Scaffolder for template-based code generation

**Status:** Accepted

**Context.** Project/file generation (e.g., a FastApp scaffold) needs templating
that sees task inputs/context, without an external generator.

**Decision.** `Scaffolder` (a `BaseTask`) copies a source tree to a destination,
transforming paths and content via Jinja/callables, with per-field render
toggles, all wired into task context.

**Consequences.** Context-aware generation that composes with downstream tasks;
no cookiecutter/yeoman dependency. Cost: another task type and template
conventions to learn.

**Alternatives rejected.** Hardcoded file copies (inflexible); cookiecutter
(external dep, standalone); Jinja-only (no composition with task inputs/XCom).

**Evidence.** **[DOCUMENTED]** `docs/task-types/file-ops.md`. **[INFERRED]**
`src/zrb/task/scaffolder.py`.

---

## ADR-0032 — Poetry, single distribution, lazy heavy imports

**Status:** Accepted

**Context.** zrb depends on many heavy, often-optional packages (pydantic-ai,
fastapi, playwright, anthropic, openai, boto3, chromadb). Importing all of them
on every CLI invocation would make startup slow.

**Decision.** Ship one Poetry-managed package (`pip install zrb`) with optional
extras; defer heavy imports to the code paths that need them, tagged with
`# lazy: <reason>` per a small set of allowed justifications.

**Consequences.** Fast CLI startup; optional capabilities cost nothing until
used; one install. Cost: contributors must follow the lazy-import discipline,
enforced socially and by `flake8 --select=F`.

**Alternatives rejected.** Namespace sub-packages (install/discovery complexity);
eager imports (startup bloat for all users).

**Evidence.** **[DOCUMENTED]** `pyproject.toml` (extras, entry point
`zrb = "zrb.__main__:serve_cli"`), `AGENTS.md` (Imports section, lazy rules).
**[INFERRED]** `# lazy:` comments throughout `src/zrb/`.

---

## ADR-0033 — Test discipline: ≥90%, public-API-only, F-only lint

**Status:** Accepted

**Context.** A framework people subclass and extend needs refactor-safe tests
and clean imports without gating on style noise.

**Decision.** Coverage ≥90%; tests exercise only public API (never `_private`
members — refactor to expose a hook if needed); `test/` mirrors `src/`; split
files >500 lines by feature, not by coverage depth; `flake8 src/zrb --select=F`
(unused/duplicate imports) runs in `./zrb-test.sh`. `.coveragerc` excludes
interfaces/`__main__`/`__init__`/`zrb_init`.

**Consequences.** Internal refactors don't break tests; imports stay clean
without style bikeshedding. Cost: testing only public surface sometimes requires
adding public hooks.

**Alternatives rejected.** Lower coverage (debt accrues); testing internals
(brittle); full flake8 ruleset (style noise; `test/` has pre-existing
unused-import noise).

**Evidence.** **[DOCUMENTED]** `AGENTS.md` (Test Guidelines), `zrb-test.sh`,
`.coveragerc`.
