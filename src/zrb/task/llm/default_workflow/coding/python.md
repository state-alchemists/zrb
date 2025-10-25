# Python Development Guide

## Core Principles
- **Follow PEP 8** unless project has specific style guides
- **Use type hints** if the project uses them
- **Match existing patterns** for imports, docstrings, and error handling

## Project Analysis
- Check for: `pyproject.toml`, `requirements.txt`, `setup.py`, `.python-version`
- Look for style guides: `.flake8`, `.pylintrc`, `ruff.toml`, `mypy.ini`
- Identify testing framework: `pytest`, `unittest`, `nose`

## Implementation Patterns
- **Imports:** Follow project's import organization (stdlib, third-party, local)
- **Error Handling:** Match existing exception patterns and logging
- **Documentation:** Use same docstring format (Google, NumPy, reStructuredText)
- **Testing:** Use project's test organization and fixtures

## Common Commands
- Formatting: `black`, `autopep8`, `yapf`
- Linting: `flake8`, `pylint`, `ruff`
- Testing: `pytest`, `python -m unittest`
- Type checking: `mypy`, `pyright`