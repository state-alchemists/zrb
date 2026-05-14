# Python Guide

## Manifest & Layout

- **Manifest**: `pyproject.toml` (preferred), `setup.py`/`setup.cfg` (legacy), `requirements*.txt`
- **Source**: `src/<package>/` (preferred) or `<package>/` at the repo root
- **Tests**: `tests/` or `test/` at the repo root; test files prefixed `test_*.py`
- **Python version**: read `pyproject.toml` `[project] requires-python` or `[tool.poetry.dependencies] python`

## Idioms

- **Type hints on public APIs.** Use `list[int]` not `List[int]` on 3.9+. Use `X | None` not `Optional[X]` on 3.10+.
- **Dataclasses for record types.** Reach for `@dataclass(frozen=True, slots=True)` before plain classes-with-init.
- **Context managers for resources.** `with open(...) as f:` — never bare `open` outside a `with`.
- **`pathlib.Path` over `os.path`.** `Path(__file__).parent / "data.json"` reads better than nested `os.path.join` calls.
- **f-strings for formatting.** Not `%` and not `.format()` in new code.
- **Generators for streams.** When the caller iterates once, return a generator (`yield`) instead of building a list.

## Common Anti-Patterns

- **Mutable default argument.** `def f(x=[])` shares the list across calls. Use `def f(x=None): x = x or []`.
- **Missing `await`.** Calling `async def` without awaiting returns a coroutine object, not the result.
- **Catching bare `Exception` or `except:`.** Swallows `KeyboardInterrupt`, hides real bugs. Catch the narrowest type.
- **`is` vs `==` confusion.** `x is None` ✓; `x is 0` is a CPython implementation detail (works by accident). Use `==` for value equality.
- **Modifying a list while iterating it.** Iterate a copy or build a new list.
- **`assert` for runtime validation.** `assert` is stripped under `python -O`. Use `if not …: raise ValueError(...)`.

## Complexity Budget Notes

- Function length ≤30 lines: counts docstring + body. Top-level decorators don't count.
- Parameters ≤4: `*args, **kwargs` each count as one. `self`/`cls` don't.
- Nesting ≤2: a single comprehension counts as one level even when it has multiple `for`/`if` clauses.

## Tests

- **Framework**: pytest
- **Naming**: `test_should_<behavior>_when_<condition>` or `test_<thing>` — match existing files
- **Run**: `pytest -x --tb=short` (stop on first failure, short traceback)
- **Coverage**: `pytest --cov=<package> --cov-report=term-missing`
- **Fixtures over setUp**: prefer `@pytest.fixture` to unittest-style `setUp`

## Lint, Format, Type-Check

- **Lint + format**: `ruff check . && ruff format --check .` (Ruff replaces flake8/isort/pyupgrade/black in modern projects)
- **Type check**: `mypy .` or `pyright .`
- **Some projects still use**: black + isort + flake8 — check `pyproject.toml`/`Makefile` and match the project's choice

## Canonical Verify Sequence

```bash
ruff check .
ruff format --check .
mypy .
pytest -x --tb=short
```

If `pyproject.toml` declares a `[tool.poetry]` or `[tool.uv]` section, prefix commands with `poetry run` or `uv run` respectively.
