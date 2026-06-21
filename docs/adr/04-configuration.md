# Configuration

The `CFG` singleton and how settings resolve. See the [ADR index](README.md)
for format and tags.

---

## ADR-0021 — `CFG` singleton composed from domain mixins, flat access

**Status:** Accepted

**Context.** zrb has 100+ tunable settings spanning LLM, web, RAG, hooks,
search, limits. One monolithic class is unnavigable; nested objects would force
churn whenever a setting moves.

**Decision.** `Config` is composed from ~12 focused mixins (one per domain:
`foundation`, `web`, `llm_core`, `llm_limits`, `llm_prompt`, …), instantiated
once as `CFG`. **Access stays flat** — `CFG.LLM_MODEL`, `CFG.WEB_HTTP_PORT` —
regardless of which mixin owns the attribute.

**Consequences.** Each domain is a small, owned file; settings can move between
mixins without touching any caller; a setting's home is discoverable from the
`config.py` lookup guide. Cost: the mixin MRO is implicit machinery to
understand.

**Alternatives rejected.** Monolithic config class (~unsearchable); hierarchical
access `CFG.llm.model` (every caller/test must change if a setting moves);
module-level constants (no env overrides or runtime setters).

**Evidence.** **[DOCUMENTED]** `src/zrb/config/config.py` docstring ("thin shell
… access stays flat"), `AGENTS.md` ("`CFG.FOO` access stays flat regardless of
which mixin owns the attribute"). **[INFERRED]** `src/zrb/config/mixins/*.py`,
`test/config/test_config.py` (all flat access).

---

## ADR-0022 — `EnvField` descriptor for env-backed config

**Status:** Accepted (introduced in the config refactor, commit `3cc15002`)

**Context.** Every env-backed setting was a hand-written `@property` getter
(read env → cast → default) plus a setter (write/delete `os.environ`) — ~4
methods of boilerplate each, error-prone to keep consistent.

**Decision.** A reusable data descriptor `EnvField(cast, serialize=…,
aliases=…, default_factory=…, nullable=…)` collapses the pattern to one line
per setting. `__get__`/`__set__` make it behave exactly like the old property,
so no caller changes.

**Consequences.** ~100 lines of boilerplate per mixin removed; uniform read
precedence and write semantics. Genuinely irregular knobs (non-prefixed keys,
post-read transforms) intentionally stay hand-written. Cost: a custom descriptor
to understand instead of plain properties.

**Alternatives rejected.** Keep hand-written properties (maintenance burden);
dataclasses (can't intercept reads/writes against live env); Pydantic
BaseSettings (over-engineered; loses direct `os.environ` control).

**Evidence.** **[DOCUMENTED]** `src/zrb/config/env_field.py` docstring (lists
exactly which knobs are *not* migrated and why). **[INFERRED]** commit
`3cc15002` "Simplify config and refactor" introduces it across all mixins;
`test/config/test_config.py` exercises get/set paths.

---

## ADR-0023 — Precedence: env var → default_factory → attribute default

**Status:** Accepted

**Context.** Config needs runtime overrides, computed defaults (one setting
derived from another, e.g. paths under `ROOT_GROUP_NAME`), and static fallbacks.

**Decision.** On read, `EnvField` resolves in order: (1) the env var
(`{PREFIX}_NAME` or an alias), (2) `default_factory(self)` computed at read
time, (3) the `DEFAULT_<NAME>` attribute set in the mixin `__init__`. Unset +
nullable → `None`; else empty string.

**Consequences.** 12-factor-style overrides, computed defaults, and discoverable
static defaults (grep `DEFAULT_`). Cost: three places to look when reasoning
about a value.

**Alternatives rejected.** Single default map (loses mixin ownership); env-or-
None (forces users to set everything); config file as primary source (adds I/O
and parsing).

**Evidence.** **[DOCUMENTED]** `src/zrb/config/env_field.py` (precedence
comments), `src/zrb/config/helper.py` (`get_env` tries names in order),
`docs/configuration/env-vars.md`.

---

## ADR-0024 — Config reads `os.environ` only; `.env` is the task layer's job

**Status:** Accepted

**Context.** Should the global config auto-load `.env` files?

**Decision.** `CFG` reads only from `os.environ` and `DEFAULT_*`. `.env` loading
is an application/task concern handled by task-level `EnvFile`, which loads into
the task context — not into global config.

**Consequences.** Config has no filesystem dependency (works in serverless/
containers); env-var precedence stays unambiguous; framework config (ports,
model) is cleanly separated from app secrets (DB passwords). Cost: users wanting
`.env` for framework config must wire it themselves.

**Alternatives rejected.** Load `.env` in `CFG.__init__` (filesystem coupling);
a `CFG.load_env_file()` method (easy to call too late); lazy auto-load (magical,
hard to debug shadowing).

**Evidence.** **[DOCUMENTED]** `docs/core-concepts/environments.md` (task-level
`EnvFile` is separate from `CFG`). **[INFERRED]** no dotenv import anywhere in
`src/zrb/config/`.

---

## ADR-0025 — `_ZRB_ENV_PREFIX` + `ROOT_GROUP_NAME` for white-labeling

**Status:** Accepted

**Context.** Organizations want to ship a rebranded CLI (`acme` instead of
`zrb`) with their own env-var namespace, without forking.

**Decision.** All config env vars are read as `{ENV_PREFIX}_NAME`, where
`ENV_PREFIX` comes from the meta-variable `_ZRB_ENV_PREFIX` (default `ZRB`,
itself never auto-prefixed — solving the bootstrap chicken-and-egg). The CLI
command name comes from `CFG.ROOT_GROUP_NAME`. A custom `__main__.py` sets both
before serving.

**Consequences.** Full rebrand from one entry point; multiple branded CLIs
coexist on one machine without env collisions. Cost: white-labelers must
remember to translate `ZRB_` to their prefix in docs/scripts.

**Alternatives rejected.** Hardcoded `ZRB`/`zrb` (forces a fork); per-distro
config file (file I/O at startup); inject prefix via `Config.__init__` (breaks
the singleton).

**Evidence.** **[DOCUMENTED]** `docs/advanced-topics/white-labeling.md`,
`docs/configuration/env-vars.md` (white-labeling note). **[INFERRED]**
`src/zrb/config/mixins/foundation.py` (`ENV_PREFIX` property reads
`_ZRB_ENV_PREFIX`), `src/zrb/runner/cli.py` (`name` → `ROOT_GROUP_NAME`).

---

## ADR-0073 — Boolean config naming: verb-first for standalone toggles, `_ENABLED` for namespace switches

**Status:** Accepted

**Context.** Boolean `CFG` knobs had drifted into two shapes — verb-first
(`WEB_ENABLE_AUTH`, `LLM_ENABLE_REWIND`) and state-last (`HOOKS_ENABLED`,
`LLM_SANDBOX_ENABLED`) — with no recorded rule, so new toggles were named ad hoc.

**Decision.** Pick the form by whether the toggle sits in a multi-setting feature
namespace:

- **`<NAMESPACE>_ENABLED`** (state-last) when the toggle is the **master switch of
  a namespace that has other settings**, so it sorts/tab-completes next to its
  siblings — e.g. `WEB_AUTH_ENABLED` (with `WEB_AUTH_ACCESS_TOKEN_EXPIRE_MINUTES`),
  `LLM_SANDBOX_ENABLED` (with `LLM_SANDBOX_ALLOW_ESCAPE`), `HOOKS_ENABLED` (with
  `HOOKS_DEBUG`/`HOOKS_TIMEOUT`).
- **Verb-first** (`ENABLE_`/`SHOW_`/`SEARCH_`/`INCLUDE_`/`ALLOW_`) for a
  **standalone on/off behavior** with no sub-config namespace — e.g.
  `LLM_ENABLE_REWIND`, `LLM_ENABLE_BUILTIN_SKILLS`/`AGENTS`, `LLM_SEARCH_PROJECT`,
  `LLM_SHOW_TOOL_CALL_DETAIL`.

`WEB_ENABLE_AUTH` was the lone violation (auth is a `WEB_AUTH_*` namespace) and
was renamed to `WEB_AUTH_ENABLED` in 2.36.0 with a back-compat alias
(`EnvField(aliases=["WEB_AUTH_ENABLED", "WEB_ENABLE_AUTH"], write_key="WEB_AUTH_ENABLED")`)
so existing configs kept working. The alias was removed in 2.39.0 — by then
users had a full release cycle to migrate, making it a safe clean break.

**Consequences.** A written rule new knobs can follow; feature settings group in
listings. Cost: the alias removal in 2.39.0 breaks any config still using
`ZRB_WEB_ENABLE_AUTH`; the rule is a heuristic, not mechanical (judgment on "is
this a namespace?").

**Alternatives rejected.** All-verb-first or all-`_ENABLED` (one loses namespace
grouping, the other reads awkwardly for standalone behaviors); leave it
undocumented (the drift that prompted this); hard rename with no alias (breaks
users' env vars — violates ADR-0025's stability intent).

**Evidence.** **[DOCUMENTED]** `AGENTS.md` (Config Conventions);
`docs/configuration/llm-config.md`, `docs/configuration/env-vars.md`.
**[INFERRED]** `src/zrb/config/mixins/web.py` (`WEB_AUTH_ENABLED`);
`src/zrb/config/env_field.py` (`aliases`/`write_key` available for back-compat).
