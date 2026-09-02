🔖 [Plan](README.md)

# Phase 0 — The rulebook

**Write no code in this phase.** Its output is two new documents plus one ADR
edit. Every later phase cites a rule number from here, so the rules must exist
first.

The second document — the pattern decision table (§0.4) — is the highest-value
item in the whole plan for onboarding. It is one page, it invents nothing, and it
answers the question a newcomer actually has.

## Why

The project has 90 ADRs and a good `AGENTS.md`, but a rule is only real if a
test enforces it or a reviewer can cite it in one line. Phases 1–9 each enforce
rules from this list. Without the list, each phase becomes a judgement call and
the drift resumes.

## R-rules (the conventions being enforced)

Copy this table verbatim into the new doc.

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

## Why the decision table matters

A contributor touching `llm/` has to hold ten orthogonal patterns
simultaneously:

| Pattern | Instances in `src/zrb` |
| --- | --- |
| `Any*` ABCs (extension points) | 13 |
| `*Mixin` classes | 16 |
| Composed parts (`self._x = X(self)`) | 18 |
| Registries | 12 |
| Managers | 15 |
| `ContextVar`s | 15 |
| `*Attr` deferred types | 7 |
| `Capability` tags | 7 |
| Lazy-import justification categories | 4 |
| `EnvField` knobs | 239 |

Each is individually justified and individually documented, across 90 ADRs and
41 doc pages. None is wrong. The volume is the tax, and no refactor in this plan
reduces it — the patterns are load-bearing.

What *does* reduce it is a single page that answers "which one do I reach for?"
so a newcomer navigates by lookup instead of by reading 2,000 lines of ADR.
Measure the counts yourself before writing it, so the table matches the tree:

```bash
cd /home/gofrendi/zrb
grep -rc "class Any" src/zrb --include="*.py" | awk -F: '{s+=$2} END{print "Any* ABCs:", s}'
grep -rhoE "class [A-Za-z]+Mixin" src/zrb --include="*.py" | wc -l
grep -rhoE "self\._(base_)?[a-z_]+ = [A-Z][A-Za-z]*\(self\)" src/zrb --include="*.py" | wc -l
grep -rn "ContextVar(" src/zrb --include="*.py" | grep -v contextvars.py | wc -l
```

## Steps

### 0.1 Create the rulebook

Create `docs/advanced-topics/framework-conventions.md`:

- Header/footer breadcrumbs matching the sibling files in that directory
  (copy the exact format from `docs/advanced-topics/maintainer-guide.md`).
- `# Framework Conventions (R1–R12)`.
- One paragraph: "These are the rules a zrb component must follow to be
  predictable. Each is enforced by a test in `test/architecture/`; the table
  names which. Cite the rule number in review."
- The R-table above, verbatim, with the "Enforced by" column changed to link the
  actual test file once each phase lands.

### 0.4 Create the pattern decision table

Create `docs/advanced-topics/which-pattern.md`. Breadcrumbs matching its
siblings; title `# Which pattern do I reach for?`.

One opening paragraph: "Ten patterns carry most of zrb. This page is a lookup
table, not a tutorial — find the row that matches what you are adding, then read
the ADR it names if you need the reasoning. Every row is enforced by a test or an
ADR; nothing here is style preference."

Then the table. Fill the "Enforced by" column from the R-rules above and the
existing tests in `test/architecture/`:

| I am adding… | Use | Not | Why / enforced by |
| --- | --- | --- | --- |
| A scalar setting a user may set from the environment or `zrb_init.py` | An `EnvField` on the matching `config/mixins/*.py` mixin, with a `DEFAULT_<NAME>` | a constructor parameter, a module-level constant | ADR-0021, ADR-0022 |
| A value that must not be read until run time | An `*Attr` type from `zrb/attr/type.py` plus `get_*_attr`, or a zero-arg callable | reading `CFG.X` in `__init__` or at module scope | ADR-0005, R3 |
| One more item in a collection users already extend (tools, prompts, skills, agents, hooks) | `append_X`/`add_X` on that family's registry | a new registry, a new constructor parameter | ADR-0091, R5/R6 |
| A whole new family of user-extensible components | A registry + a manager + a `CFG` name-allowlist twin, all three | a bare module-level list | ADR-0090, ADR-0091 |
| Behavior that any unrelated class could mix in, reading only state it sets itself | A `*Mixin` class | a composed part | ADR-0035, R11 |
| Behavior that reads state only one host provides | A composed part, `<Owner><Aspect>` in a file named for the aspect, reached through the owner's **public** accessors | a Mixin, or inheritance | ADR-0035; `test_boundaries.py` |
| A component a user may replace wholesale | An `Any*` ABC in `any_<thing>.py` **plus** a settable, non-`Any`-typed property on the host | a constructor parameter alone | R8, R9 |
| Ambient state that must follow a run without being threaded through every call | A `ContextVar` plus a typed wrapper, re-exported from `zrb/contextvars.py` | a module global, `threading.local` | ADR-0004 |
| A new agent-callable tool | A module under `llm/tool/`, **plus** registration **and** a `tag(fn, Capability.X)` in `llm/common_tools.py` | the module alone — it silently becomes `Capability.UNKNOWN`, denied in plan mode | `test/llm/test_common_tools.py` |
| A new user-executable task | A module under `builtin/`, **plus** an import in `builtin/__init__.py` **and** an `__all__` entry | the module alone — it silently never appears in the CLI | `test/builtin/test_registration_completeness.py` |
| An error the **LLM** must recover from | A `[SYSTEM SUGGESTION]` prefix naming the actionable next step | a plain `ValueError` | ADR-0057, R10 |
| An error a **user** must fix | The setting name, the bad value, and the accepted values | `raise Exception`, or a message under 40 characters | R10 |
| An import of a heavy or cyclic dependency | An in-function import with a `# lazy: <reason>` tag matching one of the four categories | a module-level import | `test_lazy_import_categories.py` |
| A decision a reasonable developer could make differently | An ADR in `docs/adr/`, and a **rewrite** of the record that owns the decision if one exists | a "supersedes ADR-NNNN" record | `docs/adr/README.md` |

### 0.5 Write the one hard call out longhand

Every row above is a lookup except **Mixin vs. part**, which is the one genuine
judgement call in the codebase: both are "a class that adds behavior to a host",
the rule is subtle, it is unenforced, and it has already drifted (the 20 config
mixins carry two naming conventions — Phase 9 Part B).

So give it its own short section on the page, phrased as a test the reader can
apply in ten seconds:

> **Ask: does this class read any attribute it does not itself set?**
>
> **No** — every piece of state it touches, it assigns. Then any class can mix it
> in, and it is a `*Mixin`. Examples: `BufferedOutputMixin`, the `CFG` mixins.
>
> **Yes** — it reads something only one host provides. Then it is a *part* of
> that host, and parts are **composed, not inherited**: the owner does
> `self._aspect = OwnerAspect(self)` and re-exposes each method as a one-line
> delegator. Examples: `LLMTaskBuilding`, `ChatExecution`, `BaseUICommands`.
>
> **How a part reaches what it needs**, cheapest first: plain data → pass it as
> an argument. One sibling's behavior → hold that sibling. Behavior spread across
> siblings or the owner → hold the owner, and read it **only** through a public
> property or method. If the owner has no public accessor for that state, add
> one; that one line is the point, not a step to skip.
>
> **Never** `self._owner._x` or `self._part._method()`. If the thing on the other
> side needs reaching, expose it.
>
> On a class users subclass (`BaseTask`, `BaseUI`), the part's attribute is
> `self._base_<aspect>`, because a subclass author will independently reach for
> the short obvious name and `super().__init__()` runs first, so their assignment
> silently wins with no error.

This is condensed from ADR-0035 and `AGENTS.md`. Do not paraphrase loosely — the
`_base_` rule and the no-private-crossing rule are both enforced by
`test/architecture/test_boundaries.py`, so getting the wording wrong sends
someone into a failing test with no explanation.

### 0.2 Link it

- `AGENTS.md` → in the `## Development Conventions` section, add two lines
  directly under the heading:
  `> New here? Start at [Which pattern do I reach for?](docs/advanced-topics/which-pattern.md).`
  `> The enforced rule list is [Framework Conventions](docs/advanced-topics/framework-conventions.md) (R1–R12). Cite rule numbers in review.`
- `CONTRIBUTING.md` → link `which-pattern.md` as the first thing a contributor
  reads after setup. Check what is already there first (`head -40 CONTRIBUTING.md`)
  and slot it in rather than duplicating an existing pointer.
- `docs/adr/README.md` → add both new docs to whichever index list already links
  `maintainer-guide.md`.
- `README.md` → the docs index there should carry `which-pattern.md` too; find
  the existing advanced-topics list and add one row.

### 0.3 Amend ADR-0091

`docs/adr/adr-0091.md` Part 2 currently permits hooks their own verb shape, and
`docs/configuration/llm-collections.md` repeats it ("Hooks are neither…
`register`"). Phase 3 removes that exception. Amend the record now so the code
change is not a violation of the ADR:

- In ADR-0091 Part 2, replace the hooks carve-out with:
  `Hooks are a name-keyed collection like skills and agents, and use the same verbs. Multiple sources co-registering on one event is a property of the value (a hook names its event), not a reason for a different verb set.`
- Per project convention (`AGENTS.md` → Architecture Decision Records), **rewrite
  the record**; do not add a superseding ADR.

## Verification

```bash
cd /home/gofrendi/zrb
test -f docs/advanced-topics/framework-conventions.md
test -f docs/advanced-topics/which-pattern.md
grep -q "framework-conventions" AGENTS.md
grep -q "which-pattern" AGENTS.md CONTRIBUTING.md README.md
grep -c "register" docs/adr/adr-0091.md   # expect 0 in the Part 2 hooks row
# every ADR the table cites must exist
grep -oE "ADR-[0-9]{4}" docs/advanced-topics/which-pattern.md | sort -u | while read a; do
  n=$(echo "$a" | cut -d- -f2); test -f "docs/adr/adr-$n.md" || echo "BROKEN CITATION: $a"
done
# every test the table cites must exist
grep -oE "test_[a-z_]+\.py" docs/advanced-topics/which-pattern.md | sort -u | while read t; do
  find test -name "$t" | grep -q . || echo "BROKEN TEST CITATION: $t"
done
./zrb-test.sh   # docs-only change; must stay green
```

**The two citation checks are not optional.** A decision table that points at a
missing ADR or a deleted test is worse than no table — it costs the reader the
trust they need to use it at all.

## Done when

- `docs/advanced-topics/framework-conventions.md` exists with R1–R12.
- `docs/advanced-topics/which-pattern.md` exists with all 14 rows plus the
  Mixin-vs-part section, and every ADR and test it cites resolves.
- `AGENTS.md`, `CONTRIBUTING.md` and `README.md` all link `which-pattern.md`.
- ADR-0091 no longer grants hooks a verb exception.

🔖 [Plan](README.md)
