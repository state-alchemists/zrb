🔖 [Plan](README.md)

# Phase 9 — Typed errors and one naming convention

Enforces **R10**, **R11**. Risk: low. Estimate: 1 day. Ship this any time.

## Part A — Errors (R10)

### A.1 The audit

```bash
cd /home/gofrendi/zrb
grep -rhoE "raise [A-Za-z]+" src/zrb --include="*.py" | sort | uniq -c | sort -rn | head
grep -rn "raise Exception" src/zrb --include="*.py"
grep -rnE 'raise (ValueError|RuntimeError|TypeError)\("[^"]{0,25}"\)' src/zrb --include="*.py"
```

Measured at 2.69.0. The error story is in better shape than the rest — 143
`[SYSTEM SUGGESTION]` sites, 53 `ValueError`, 32 `RuntimeError` — with two
pockets left:

**13 `raise Exception`:**

| Site | Count |
| --- | --- |
| `llm/tool/search/http_errors.py` | 4 |
| `llm/tool/search/searxng.py` | 3 |
| `llm/tool/search/brave.py` | 2 |
| `llm/tool/search/google_rss.py` | 2 |
| `llm/tool/search/serpapi.py` | 1 |
| `builtin/changelog.py:104` | 1 |

**4 messages under 25 characters, with no context:**

| Site | Message |
| --- | --- |
| `llm/task/chat/running.py:226` | `"No UI available"` |
| `builtin/git_subtree.py:62` | `"No subtree config found"` |
| `builtin/git_subtree.py:94` | `"No subtree config found"` |
| `util/todo/model.py:18` | `"Invalid priority format"` |

### A.2 Fix the search tools

All 12 search-tool raises are HTTP/API failures the **LLM** reads and must
recover from, so they take the ADR-0057 form. Start with
`llm/tool/search/http_errors.py` — the other four modules delegate to it, so
fixing it first shrinks the rest.

```python
raise ToolError(
    "[SYSTEM SUGGESTION] The Brave Search API returned 401 Unauthorized. "
    "The key in BRAVE_API_KEY is missing or invalid. Tell the user to set it, "
    "or use a different search tool."
)
```

Define one exception type next to the tools rather than importing `Exception`:

```python
class SearchToolError(RuntimeError):
    """A search backend failed in a way the agent should report and route around."""
```

`RuntimeError` is the right base — this is a failed operation, not a bad
argument. Check whether the project already has a tool-error type before adding
one: `grep -rn "class .*Error" src/zrb/llm/tool/ src/zrb/llm/`. If
`SandboxUnavailableError` or similar sits in a shared place, put `SearchToolError`
beside it.

### A.3 Fix `builtin/changelog.py:104`

`raise Exception(f"git tag failed with exit code {code}")` is a *maintainer*
error, not an agent one. No `[SYSTEM SUGGESTION]`; name what failed and what to
do:

```python
raise RuntimeError(
    f"`git tag` exited {code}. Check that the tag does not already exist "
    f"and that the working tree is clean."
)
```

### A.4 Fix the four bare messages

Each must name the setting, the bad value and what is accepted (R10):

| Site | Replacement message |
| --- | --- |
| `llm/task/chat/running.py:226` | `f"Task {self.name!r} has no UI. An interactive session needs one — pass ui=... , append_ui_factory(...), or leave include_default_ui=True."` — read the surrounding code to confirm the real remedies before writing them |
| `builtin/git_subtree.py:62,94` | Name the file it looked in and the command that creates the config |
| `util/todo/model.py:18` | Show the offending value and the accepted form (`"(A)"`–`"(Z)"`, or whatever the parser accepts — read `model.py` first) |

Do **not** guess a remedy. If you cannot tell from the code what the user should
do, that is the finding; say so in the commit message and write the message with
only the facts you can verify.

### A.5 Ratchet (R10)

Add to `test/architecture/test_boundaries.py`:

```python
def test_no_bare_exception_is_raised():
    """R10. `Exception` tells a caller nothing and cannot be caught selectively."""
    # AST-walk src/zrb for ast.Raise whose exc is a Call to Name(id="Exception").


def test_no_error_message_is_shorter_than_forty_characters():
    """R10. A message that fits in a tweet cannot name the setting, the bad
    value and the remedy. Constant-string raises only — an f-string or a
    variable is assumed to carry context."""
    # AST-walk for ast.Raise -> Call -> args[0] is a bare ast.Constant str
    # under 40 chars. Exemptions dict with a one-line reason each.
```

Run both **before** fixing, to see the true counts (expect 13 and 4, plus
possibly a few the greps above missed because they span lines):

```bash
pytest test/architecture/test_boundaries.py -k "bare_exception or error_message" 2>&1 | tail -40
```

40 characters is arbitrary but calibrated: it is longer than all four current
offenders and shorter than every message that already names a remedy. If it
turns out to flag good messages, lower it once — do not start an exemption list
to defend a bad threshold.

## Part B — Naming (R11)

### B.1 The mixin split

```bash
grep -hn "^class " src/zrb/config/mixins/*.py
```

Twenty config mixins, two conventions, split 12/8:

| `<Thing>Mixin` (12) | `Config<Thing>` (8) |
| --- | --- |
| `FoundationMixin`, `WebMixin`, `LLMCoreMixin`, `LLMUIMixin`, `LLMLimitsMixin`, `LLMSandboxMixin`, `RAGMixin`, `InternetSearchMixin`, `HooksMixin`, `TaskRuntimeMixin`, `ThemeMixin`, `LLMUIRuntimeMixin`, `LLMUICommandsMixin`, `LLMVoiceMixin` | `ConfigLLMContent`, `ConfigLLMPrompt`, `ConfigLLMSearch`, `ConfigLLMTools`, `ConfigCLIStyle`, `ConfigLLMUIStyles` |

(The counts differ slightly from 12/8 because two files declare more than one
class — take the grep output as authoritative.)

**Standardize on `<Thing>Mixin`.** Three reasons: it is the majority, it matches
`AGENTS.md`'s rule that `Mixin` means reusable, and `Config<Thing>` reads like a
noun ("a config-LLM-content") rather than a role. So:

- `ConfigLLMContent` → `LLMContentMixin`
- `ConfigLLMPrompt` → `LLMPromptMixin`
- `ConfigLLMSearch` → `LLMSearchMixin`
- `ConfigLLMTools` → `LLMToolsMixin`
- `ConfigCLIStyle` → `CLIStyleMixin`
- `ConfigLLMUIStyles` → `LLMUIStylesMixin`

These are internal (only `config/config.py` and their own test files import
them), so the diff is small:

```bash
grep -rn "ConfigLLMContent\|ConfigLLMPrompt\|ConfigLLMSearch\|ConfigLLMTools\|ConfigCLIStyle\|ConfigLLMUIStyles" src/zrb test docs
```

Update the `config/config.py` module docstring map at the same time — it lists
each mixin by file, and the class names appear in the import block right below it.

### B.2 The `# noqa: E501` on `Config`

```bash
sed -n '46,52p' src/zrb/config/config.py
```

The `Config` class declaration carries a ~200-character trailing comment
explaining a pyright false positive about property-vs-attribute overrides. It is
the single least readable line in the config package, and it is the first thing a
maintainer reads when opening the file.

Move the explanation into the class docstring (which already exists, right
below) as a short `Note:` paragraph, and leave only what the linter needs on the
declaration line. If the `noqa` becomes unnecessary once the comment is gone —
likely, since the line is only long *because* of the comment — delete it.
Verify: `flake8 src/zrb --select=E501,F` and `pyright src/zrb`.

### B.3 One garbled docstring

```bash
grep -n "genomic" src/zrb/llm/prompt/registry.py
```

`PromptRegistry`'s class docstring reads "``default`` (constructor genomic
argument)". The intended word is "keyword". Fix it. Then grep the tree for
similar artifacts, since one usually means several:

```bash
grep -rniE "\b(genomic|prehensile|onomatopoeic)\b" src/zrb docs/adr docs/configuration
```

Small, but it is the exact tax the goal names: a maintainer stops, re-reads,
and wonders what they are missing.

### B.4 Ratchet (R11)

Add to `test/architecture/test_boundaries.py`:

```python
def test_config_mixins_share_one_naming_convention():
    """R11. Sibling classes in one package use one convention."""
    names = [...]   # every top-level class in src/zrb/config/mixins/
    offenders = [n for n in names if not n.endswith("Mixin")]
    assert not offenders, f"{offenders} should end in 'Mixin' (R11, ADR-0035)."
```

## Verification

```bash
cd /home/gofrendi/zrb
grep -rn "raise Exception" src/zrb --include="*.py"                    # expect none
grep -rn "genomic" src/zrb                                             # expect none
grep -hn "^class " src/zrb/config/mixins/*.py | grep -v "Mixin"        # expect none
flake8 src/zrb --select=E501,F
pyright src/zrb
pytest test/architecture/ -q
./zrb-test.sh
```

## Done when

No `raise Exception` in `src/zrb`, no constant error message under 40
characters (or each exemption carries a reason), every config mixin ends in
`Mixin`, the `Config` declaration line is readable, and `./zrb-test.sh` is green.

🔖 [Plan](README.md)
