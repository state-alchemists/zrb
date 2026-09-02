🔖 [Plan](README.md)

# Phase 6 — One config object, not two

Enforces **R12**. Risk: medium. Estimate: 2 days.

## The problem

There are two things called config, and a user cannot guess which to set.

```bash
cd /home/gofrendi/zrb
sed -n '1,50p' src/zrb/llm/config/config.py
grep -rn "llm_config" src/zrb --include="*.py" | wc -l
```

`LLMConfig` (`src/zrb/llm/config/config.py`, 254 lines, exported from
`zrb/__init__.py` as the singleton `llm_config`) holds `model`, `small_model`,
`multimodal_model`, `model_settings`, `system_prompt`, `summarization_prompt`,
`api_key`, `base_url`, `provider`, `model_getter`, `model_renderer`.

Every one of those is *also* a `CFG` knob or a registry. And the fallback chain
is written by hand, per property:

```python
@property
def model(self) -> "str | Model":
    if self._model is not None:
        return self._model
    model_name = CFG.LLM_MODEL or "openai-chat:gpt-4o"     # <- third default
    return self._resolve_model_by_name(model_name)
```

So `CFG.LLM_MODEL` has a documented default, and `llm_config.model` has a
*different* hardcoded one (`"openai-chat:gpt-4o"`) that wins when `CFG.LLM_MODEL`
is empty. Confirm:

```bash
grep -n "openai-chat:gpt-4o" src/zrb/llm/config/config.py
grep -n "DEFAULT_LLM_MODEL" src/zrb/config/mixins/llm_core.py
```

Three questions a user cannot answer from the names: Do I set `CFG.LLM_MODEL` or
`llm_config.model`? If I set both, which wins? Why is there an `llm_config`
at all, given `CFG` has an `LLM_` namespace?

## What `LLMConfig` actually is

Read it before deciding. It does two separable jobs:

1. **An override layer over `CFG`** — the `_model`/`_api_key`/`_base_url`
   fields and their `if self._x is not None` fallbacks. This is ADR-0090's
   layering, hand-written eleven times.
2. **A model resolver** — `_resolve_model_by_name`, `resolve_model`,
   `_resolve_provider`, turning a `"provider:name"` string plus credentials into
   a `pydantic_ai` `Model` object. This job is real, non-trivial, and has nothing
   to do with configuration.

Job 1 is redundant with `CFG` plus the Phase 4 slots. Job 2 is not.

## Step 6.1 — Split the two jobs

Create `src/zrb/llm/config/model_resolver.py`:

```python
class ModelResolver:
    """Turns a model name plus credentials into a pydantic-ai `Model`.

    Pure resolution: it reads nothing and stores nothing. Give it a name and
    the credentials to use; it returns a `Model` (or the name unchanged when
    the provider is a plain string).
    """

    def resolve(
        self,
        model: "str | Model | None" = None,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        provider: "str | Provider | None" = None,
    ) -> "str | Model": ...
```

Move `_resolve_model_by_name`, `resolve_model` and `_resolve_provider` into it
verbatim, changing only how they obtain `api_key`/`base_url`/`provider` — from
arguments instead of `self._api_key`/`CFG`. Keep the `pydantic_ai` imports lazy
with the existing `# lazy:` tags (category 1, heavy third-party) —
`test/architecture/test_lazy_import_categories.py` enforces the tag.

Export a module-level `model_resolver = ModelResolver()` and register it in
`zrb/__init__.py` alongside the other singletons.

## Step 6.2 — Move the settings to `CFG`

For each `LLMConfig` field, check whether a `CFG` twin already exists:

```bash
python - <<'EOF'
from zrb.config.config import CFG
for name in ["LLM_MODEL", "LLM_SMALL_MODEL", "LLM_MULTIMODAL_MODEL", "LLM_MODEL_SETTINGS",
             "LLM_SYSTEM_PROMPT", "LLM_SUMMARIZATION_PROMPT", "LLM_API_KEY",
             "LLM_BASE_URL", "LLM_PROVIDER"]:
    print(f"{name:28} {'exists' if hasattr(type(CFG), name) else 'MISSING'}")
EOF
```

- **Exists** → delete the `LLMConfig` property; callers read `CFG.<NAME>`.
- **Missing and scalar** → add an `EnvField` to `src/zrb/config/mixins/llm_core.py`
  following the surrounding style, with a `DEFAULT_<NAME>`. Match the existing
  default; do not carry the `"openai-chat:gpt-4o"` string over unless
  `DEFAULT_LLM_MODEL` is empty, in which case make it the documented default in
  **one** place.
- **Missing and not a scalar** (`model_settings` is a `ModelSettings` object;
  `model_getter` / `model_renderer` are callables) → these are **components**,
  not config. Per ADR-0090 Part 3 they are set through a slot, not `CFG`. They
  become Phase 4 slots on the task (`model_settings`) or are deleted if unused:
  ```bash
  grep -rn "model_getter\|model_renderer" src/zrb test docs --include="*.py" --include="*.md"
  ```
  If either has no caller outside `LLMConfig` itself, delete it — a hook nobody
  uses is a hook nobody maintains.

## Step 6.3 — Retire `llm_config`

The 40-odd call sites split into three shapes. Handle each mechanically:

```bash
grep -rn "llm_config" src/zrb --include="*.py"
```

| Call shape | Becomes |
| --- | --- |
| `llm_config.model` / `.small_model` / `.multimodal_model` | `CFG.LLM_MODEL` etc., then `model_resolver.resolve(...)` at the point of use |
| `llm_config.resolve_model(x)` | `model_resolver.resolve(x, api_key=CFG.LLM_API_KEY, base_url=CFG.LLM_BASE_URL, provider=CFG.LLM_PROVIDER)` |
| `LLMTask(llm_config=...)` / `self._llm_config` | The per-task override is now the Phase 4 `model` / `model_settings` slots. Delete the parameter. |

Sites to expect (measured): `llm/task/shared_getters.py:58,70`,
`llm/task/llm_task.py:32,115,239,628,844`, `llm/task/chat/task.py:33,115,315,516`,
`llm/agent/summarizer.py:4,18,19`, `llm/agent/common.py:20,515,521`,
`llm/tool/web.py:13,489`, `llm/tool/code.py:11,329,410`,
`llm/agent/run/runner.py:73,944`, `llm/ui/base/exec_commands.py:211,213`,
`llm/config/__init__.py`, `zrb/__init__.py:76,120,125,195`.

**The `resolve_model(...)` repetition is the sign you got the split right or
wrong.** If the same four-argument call appears at ten sites, add one
convenience function next to the resolver:

```python
def resolve_configured_model(model: "str | Model | None" = None) -> "str | Model":
    """Resolve *model* (or `CFG.LLM_MODEL`) using the configured credentials."""
    return model_resolver.resolve(
        model or CFG.LLM_MODEL,
        api_key=CFG.LLM_API_KEY,
        base_url=CFG.LLM_BASE_URL,
        provider=CFG.LLM_PROVIDER,
    )
```

and call *that* from the ten sites. One function reading `CFG` is the layering;
ten hand-written `if x is not None` chains was the problem.

Then delete `src/zrb/llm/config/config.py`, remove `LLMConfig`/`llm_config` from
`src/zrb/llm/config/__init__.py` and `src/zrb/__init__.py` (`__all__` too), and
remove the `llm_config` constructor parameter from both task classes.

**Clean break, no shim** — project convention. This is a breaking change for
anyone whose `zrb_init.py` sets `llm_config.model`; the changelog entry must give
the one-line migration (`llm_config.model = X` → `CFG.LLM_MODEL = X`).

## Step 6.4 — Ratchet (R12)

Add to `test/architecture/test_mutation_surface.py`:

```python
def test_there_is_exactly_one_configuration_object():
    """`CFG` is the only config object. A second one means a user has to guess."""
    import zrb
    offenders = [
        name for name in zrb.__all__
        if name.endswith("_config") and name != "CFG"
    ]
    assert not offenders, (
        f"{offenders} are exported alongside CFG. Scalars live on CFG (ADR-0021/0022); "
        "components live in registries or slots (ADR-0090). R12."
    )
```

`web_auth_config` (`src/zrb/config/web_auth_config.py`, 209 lines) will trip
this. Check whether it is exported from `zrb/__init__.py`:
`grep -n "web_auth_config" src/zrb/__init__.py`. If it is, it is the same
problem in the web subsystem and should be folded into `CFG` the same way —
but that is **out of scope here**. Either add it as a documented exemption with
a TODO naming a follow-up, or fold it in if it turns out to be a thin wrapper
over `CFG.WEB_AUTH_*` (read it first; it may already be one).

## Step 6.5 — Docs

- `docs/configuration/llm-config.md` (931 lines) is the main casualty. Grep for
  `llm_config` and rewrite every example to `CFG.LLM_*`.
- `docs/configuration/env-vars.md` — add any knobs created in Step 6.2.
- Changelog: breaking, with the migration table.

## Verification

```bash
cd /home/gofrendi/zrb
grep -rn "llm_config" src/zrb docs/ --include="*.py" --include="*.md" | grep -v changelog
# expect no output
python -c "
from zrb import CFG
from zrb.llm.config.model_resolver import resolve_configured_model
CFG.LLM_MODEL='anthropic:claude-opus-5'
print(resolve_configured_model())
"
pytest test/architecture/test_mutation_surface.py -q
./zrb-test.sh
```

## Done when

`llm_config` is gone from `src/zrb` and the live docs, `CFG` is the only exported
config object (or `web_auth_config` carries a documented exemption with a
follow-up), the `"openai-chat:gpt-4o"` second default is gone, and
`./zrb-test.sh` is green.

## As implemented (divergences from this plan)

Landed as `40cd14ab3` ("Phase 6: delete LLMConfig/llm_config, make CFG +
ModelResolver the only LLM config surface (R12)"). The split into
`ModelResolver` plus `CFG` scalars, and the `web_auth_config` exemption,
landed exactly as written. Six things the plan didn't anticipate:

- **`small_model`/`multimodal_model` needed a concurrency fix this plan never
  raised.** §6.3's table treats them as plain scalars (`llm_config.small_model`
  → `CFG.LLM_SMALL_MODEL`). But `LLMConfig`'s setters were process-wide
  global state — the `/model small ...`/`/model multimodal ...` slash
  commands wrote to the single shared `llm_config` singleton, so two
  concurrent chat sessions in one process (e.g. two web-UI users) could leak
  each other's model-tier choice. A straight `CFG.LLM_SMALL_MODEL = x` write
  from the command handler would have faithfully preserved that bug, not
  introduced it, but it's a bug worth actually fixing while every call site
  is already being touched. Fixed with two new per-run `ContextVar`s
  (`current_small_model`, `current_multimodal_model` in `agent_state.py`),
  bound from the UI's own `small_model`/`multimodal_model` at the start of
  `run_agent()` — the same pattern `current_ui`/`current_yolo` already use.
  `src/zrb/contextvars.py` (the canonical `ContextVar` index) and its
  pinning test, plus the maintainer-guide/architecture doc counts, needed
  updating too (fourteen → sixteen `ContextVar`s) — none of this is in the
  plan's scope list. `MultiUI` does not yet proxy these two attributes to
  its children — a narrow, documented limitation, not fixed here.
- **Three convenience functions were needed, not the one §6.3 sketches.**
  `resolve_configured_model`/`_small_model`/`_multimodal_model` each encode a
  different fallback shape: small falls back to `CFG.LLM_MODEL` when unset;
  multimodal returns `None` (callers drop the attachment with a warning)
  rather than falling back to anything. A single `resolve_configured_model`
  function, as the plan sketches, can't express either without the caller
  re-deriving the fallback by hand at every site — exactly the repetition
  Step 6.3 says is "the sign you got the split right or wrong."
- **`model_settings`, `system_prompt`, and `summarization_prompt` were pure
  dead code, not fields needing a `CFG` twin or a slot.** §6.2 anticipated
  `model_settings` might need to become a Phase-4-style task slot (it already
  is one, independently, on `LLMTask`/`LLMChatTask` — `LLMConfig`'s copy had
  no reader anywhere outside itself). `system_prompt`/`summarization_prompt`
  were assigned in `LLMConfig.__init__` but never read by anything. All three
  were deleted with no replacement, not migrated.
- **§6.3's "sites to expect" list covered a fraction of the actual call
  sites.** Real files touched beyond that list: `builtin/changelog.py`,
  `builtin/llm/please.py`, `llm/hook/creator.py`,
  `llm/hook/journal_compliance.py`, `llm/voice/engine.py`,
  `llm/util/multimodal_describe.py`, `llm/agent/subagent/manager.py`,
  `llm/agent/types.py` (a docstring reference). Each site's raise-vs-fall-back
  and raw-name-vs-resolved-value semantics had to be traced individually —
  a blind mechanical substitution using the plan's table would have gotten
  several of these wrong (e.g. multimodal's None-means-unconfigured case).
- **Test fallout was much larger than the plan's Verification section
  implies.** `test/llm/config/test_llm_config.py` (596 lines, ~62 tests)
  had to be deleted outright and replaced with a new
  `test/llm/config/test_model_resolver.py` covering `ModelResolver`'s actual
  surviving behavior — not a port, since most of the old file tested
  config-layering properties that no longer exist. A further ~13 test files
  across `test/llm/agent/`, `test/llm/hook/`, `test/llm/task/`,
  `test/llm/util/`, `test/llm/voice/`, and `test/llm/ui/` had mock patches
  targeting `llm_config`/`default_llm_config`/`LLMConfig` that needed
  rewriting to patch the new functions/properties instead. None of this is
  mentioned in the plan.
- **Two architecture ratchets outside `test_mutation_surface.py` needed
  budget bumps**: `test_constructor_surface.py`'s `PARAM_BUDGETS` (net +1
  each on `LLMTask`/`LLMChatTask` — `model_getter`+`model_renderer` replacing
  the single `llm_config` param) and `test_facade_size_budget.py`'s budget
  for `llm/task/llm_task.py` (900 → 910). The public API snapshot
  (`test/public_api_snapshot.json`) also needed regenerating via
  `ZRB_UPDATE_API_SNAPSHOT=1` — not called out in the plan's Verification
  section, which only lists `test_mutation_surface.py` and `./zrb-test.sh`.
  Docs beyond §6.5's two named files also needed sweeping:
  `docs/task-types/llmchat-task.md`, `docs/configuration/llm-collections.md`,
  `docs/advanced-topics/hooks.md`. `docs/configuration/env-vars.md` turned
  out to need no changes at all — `LLM_MODEL`/`LLM_PROVIDER` are documented
  in `llm-config.md`, not there.

🔖 [Plan](README.md)
