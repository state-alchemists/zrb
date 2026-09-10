🔖 [Documentation Home](../../README.md) > [Contributing](./) > Which pattern do I reach for?

# Which pattern do I reach for?

Ten patterns carry most of zrb. This page is a lookup table, not a tutorial — find the row that matches what you are adding, then read the ADR it names if you need the reasoning. Every row is enforced by a test or an ADR; nothing here is style preference.

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

## The one hard call: Mixin vs. part

Every row above is a lookup except this one, which is the one genuine judgement call in the codebase: both a `Mixin` and a part are "a class that adds behavior to a host," the rule is subtle, and it is unenforced by any single test on its own — it relies on the boundary tests plus review.

> **Ask: does this class read any attribute it does not itself set?**
>
> **No** — every piece of state it touches, it assigns. Then any class can mix it in, and it is a `*Mixin`. Examples: `BufferedOutputMixin`, the `CFG` mixins.
>
> **Yes** — it reads something only one host provides. Then it is a *part* of that host, and parts are **composed, not inherited**: the owner does `self._aspect = OwnerAspect(self)` and re-exposes each method as a one-line delegator. Examples: `LLMTaskBuilding`, `ChatExecution`, `BaseUICommands`.
>
> **How a part reaches what it needs**, cheapest first: plain data → pass it as an argument. One sibling's behavior → hold that sibling. Behavior spread across siblings or the owner → hold the owner, and read it **only** through a public property or method. If the owner has no public accessor for that state, add one; that one line is the point, not a step to skip.
>
> **Never** `self._owner._x` or `self._part._method()`. If the thing on the other side needs reaching, expose it.
>
> On a class users subclass (`BaseTask`, `BaseUI`), the part's attribute is `self._base_<aspect>`, because a subclass author will independently reach for the short obvious name and `super().__init__()` runs first, so their assignment silently wins with no error.

This is condensed from ADR-0035 and `AGENTS.md`. Do not paraphrase loosely — the `_base_` rule and the no-private-crossing rule are both enforced by `test/architecture/test_boundaries.py`, so getting the wording wrong sends someone into a failing test with no explanation.

See also: [Framework Conventions (R1–R12)](framework-conventions.md).

---

🔖 [Documentation Home](../../README.md) > [Contributing](./) > Which pattern do I reach for?
