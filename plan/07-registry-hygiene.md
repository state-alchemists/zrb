🔖 [Plan](README.md)

# Phase 7 — Two leftovers ADR-0090 named and never cleaned up

Enforces **R12** and ADR-0035. Risk: medium. Estimate: 2 days.

ADR-0090's Context section lists the "ad-hoc internal registries" it intended to
retire and admits the migration is follow-on work. Two are still there.

## Part A — `_ProviderRegistry` is not a registry

```bash
cd /home/gofrendi/zrb
sed -n '38,74p' src/zrb/llm/prompt/manager.py
grep -n "_live_context_providers\|_ProviderRegistry" src/zrb/llm/prompt/manager.py
```

`_ProviderRegistry` (`llm/prompt/manager.py:38`, ~30 lines) is instantiated once
at line 157 as `self._live_context_providers`, written by `add_live_context`
(line 283) and read by `compose_prompt` (line 337). ADR-0090 names it as an
ad-hoc registry to migrate.

**Do not promote it to a public registry.** Read what it is: an ordered,
name-keyed list of live-context callables owned by one `PromptManager`, with no
`CFG` twin, no discovery layer, and no layering. It fails every clause of the
ADR-0090 definition of a registry. Making it one would add a sixth family, a
`CFG.LLM_LIVE_CONTEXT` twin and a module singleton to serve a single call site —
that is the over-engineering the goal is trying to get away from.

**The problem is the name and the verbs, not the design.** Fix those:

1. Rename the class `_ProviderRegistry` → `LiveContextProviders` and move it to
   `src/zrb/llm/prompt/live_context_providers.py`. It is a *part* in the
   ADR-0035 sense — `PromptManager` composes it — so it is public (parts are
   imported across modules; the leading underscore is a false claim). Name it for
   its aspect, in a file named for the aspect, as `AGENTS.md` requires.
2. Give it the R6 name-keyed verb set, replacing `set` and `render`:
   - `add_provider(name, provider)` — replaces any provider under `name`
     (current `set` behavior, correctly named)
   - `remove_provider(name)`
   - `set_providers(providers)` — wholesale replacement
   - `get_providers()` — the `(name, provider)` pairs
   - `render(ctx)` — keep; it is the resolution step, not a mutation
3. The `label` constructor argument exists only for the log message. It has one
   caller passing `"Live-context"`. Delete it and hardcode the string in the log
   line — a parameter with one possible value is not configuration.

`PromptManager.add_live_context` (the public API, line 275) keeps its name and
becomes a one-line delegator to `add_provider`. Add the missing siblings
(`remove_live_context`, `set_live_contexts`, `get_live_contexts`) so R6 holds at
the public surface too — that is what Phase 3's ratchet will check.

Update the ADR-0090 Context paragraph: `_ProviderRegistry` is no longer in the
list of registries to migrate, because it was never a registry.

## Part B — `SubAgentManager` does two jobs

```bash
grep -nE "^    def [a-z]|^    @property" src/zrb/llm/agent/subagent/manager.py
wc -l src/zrb/llm/agent/subagent/manager.py
```

482 lines, and the method list splits cleanly in two:

| Roster (what a manager is, per ADR-0090) | Construction (what a manager is not) |
| --- | --- |
| `registry`, `reload`, `scan`, `search_dirs` | `create_agent` |
| `add_agent`, `remove_agent`, `set_agents` | `create_llm_chat_task` |
| `get_agents`, `get_agent_definition` | `resolve_agent_build` |
| `append_tool`, `append_tool_factory`, `append_toolset`, `append_toolset_factory` | `get_tool_registry`, `get_tool_factories`, `get_all_toolsets` |

Compare with its sibling `SkillManager` (491 lines but one job: `registry`,
`reload`, `scan`, `search_dirs`, `add_skill`, `remove_skill`, `set_skills`,
`get_skills`, `get_skill`, `get_skill_content`). `SkillManager` is the shape the
convention describes; `SubAgentManager` is that plus a factory bolted on.

### Step B.1 — Extract the builder

Create `src/zrb/llm/agent/subagent/building.py` with
`class SubAgentBuilding` — the ADR-0035 part naming (`<Owner><Aspect>`, file
named for the aspect, like `ChatExecution` in `task/chat/execution.py`):

```python
class SubAgentBuilding:
    """Builds a runnable sub-agent from a definition in the roster.

    Composed by `SubAgentManager`, which owns the roster; this part owns
    turning one entry of that roster into an agent or an `LLMChatTask`.
    """

    def __init__(self, owner: "SubAgentManager") -> None:
        self._owner = owner
```

Move `create_agent`, `create_llm_chat_task`, `resolve_agent_build` and the tool
plumbing (`get_tool_registry`, `get_tool_factories`, `get_all_toolsets`,
`append_tool*`, `append_toolset*`) into it.

Follow the ADR-0035 access rules exactly — this is the part of the phase most
likely to be done wrong:

- The part reaches the manager only through **public** names:
  `self._owner.get_agent_definition(...)`, never `self._owner._agents`.
  If it needs state with no public accessor, **add the accessor** — that
  one-line cost is the point.
- Type the constructor parameter as the real `SubAgentManager` class (no
  `TYPE_CHECKING` host-contract block; the project removed those).
- The manager holds it as `self._building = SubAgentBuilding(self)` and
  re-exposes every moved method as a **one-line delegator**, so no external call
  site changes.
- `SubAgentManager` is not a base class users subclass, so the attribute is
  `self._building`, not `self._base_building`.

`test/architecture/test_boundaries.py::test_no_part_reaches_another_objects_private_state`
enforces the private-access rule. Run it after each move, not at the end.

### Step B.2 — Watch the circular import

`SubAgentBuilding.create_llm_chat_task` imports `LLMChatTask`, which imports
back into the agent subsystem. The existing code already handles this; check how
before you move it:

```bash
grep -n "lazy:" src/zrb/llm/agent/subagent/manager.py
cat test/architecture/test_circular_import_allowlist.py | sed -n '1,80p'
```

Carry the `# lazy:` tags over verbatim. If the split creates a *new* cycle,
`test_circular_import_allowlist.py` will fail — add the entry to the allowlist
with the cycle named, or restructure. Do not silence it.

### Step B.3 — Align `search_dirs` (finishes Phase 3's R7 work)

Phase 3 Step 3.1 decided: every manager exposes a settable `search_dirs`
property; `SubAgentManager.root_dir` is a different concept (the scan root) and
is renamed `scan_root`. Verify that reading is right before renaming:

```bash
sed -n '105,135p' src/zrb/llm/agent/subagent/manager.py
```

If `root_dir` turns out to *be* the search directory rather than the scan root,
delete it in favor of `search_dirs` instead of renaming it.

## Step 7.1 — Ratchet

Add to `test/architecture/test_mutation_surface.py`:

```python
MANAGER_ROSTER_API = ("registry", "reload", "scan", "search_dirs")


def test_managers_expose_the_same_roster_api():
    """A manager is a roster resolver. Five families, one shape (ADR-0090)."""
    for path in ("zrb.llm.skill.manager:skill_manager",
                 "zrb.llm.agent.subagent.manager:sub_agent_manager",
                 "zrb.llm.hook.manager:hook_manager"):
        manager = _load(path)
        missing = [n for n in MANAGER_ROSTER_API if not hasattr(manager, n)]
        assert not missing, f"{path} is missing {missing} (R6/R7, ADR-0090)"
```

`PromptManager` is deliberately excluded — ADR-0090 Part 1 states it is a
resolved per-task view, not a roster owner. Say so in a comment so the next
reader does not "fix" it.

Also extend `test/architecture/test_facade_size_budget.py` with the new numbers
once the split lands; `subagent/manager.py` should drop well under 482 lines.

## Step 7.2 — Docs

- ADR-0090 Context: drop `_ProviderRegistry` from the ad-hoc registry list and
  add one clause saying it was reclassified as a part, not migrated.
- `AGENTS.md` "Inside `llm/`" table: the `agent/` row says
  "`subagent/` handles delegation" — still true, no change needed. Confirm.
- Changelog: internal refactor plus the `add_live_context` sibling additions.
  The `_ProviderRegistry` rename is private-to-public, so note the new import
  path for anyone who reached into it.

## Verification

```bash
cd /home/gofrendi/zrb
grep -rn "_ProviderRegistry" src/zrb docs/ | grep -v changelog   # expect no output
wc -l src/zrb/llm/agent/subagent/manager.py src/zrb/llm/agent/subagent/building.py
pytest test/architecture/ -q
python -c "
from zrb.llm.prompt.manager import PromptManager
pm = PromptManager()
pm.add_live_context('x', lambda ctx: 'hello')
assert 'x' in dict(pm.get_live_contexts())
pm.remove_live_context('x')
assert 'x' not in dict(pm.get_live_contexts())
print('ok')
"
./zrb-test.sh
```

## Done when

`_ProviderRegistry` no longer exists by that name, `SubAgentManager` exposes only
the roster API with construction delegated to `SubAgentBuilding`, all three
managers answer `search_dirs`, and `./zrb-test.sh` is green.

🔖 [Plan](README.md)
