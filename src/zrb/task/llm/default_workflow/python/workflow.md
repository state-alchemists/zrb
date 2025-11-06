---
description: "A workflow for developing with Python, including project analysis and best practices."
---
# Python Development Guide

This guide provides the baseline for Python development. It is superseded by project-specific conventions.

## 1. Project Analysis Checklist

Before coding, inspect the project for these files to determine its conventions:

- **Dependency Management:** `pyproject.toml` (and `poetry.lock` or `pdm.lock`), `requirements.txt`, `setup.py`. Note the exact libraries and versions used.
- **Virtual Environment:** Check for a `.venv` or `venv` directory. If it exists, activate it using `source .venv/bin/activate`. If not, create one using `python -m venv .venv` and then activate it.
- **Python Version:** Look for a `.python-version` file or check `pyproject.toml`.
- **Style & Linting Config:** `ruff.toml`, `pyproject.toml` (for `black`, `isort`, `ruff`), `.flake8`, `.pylintrc`. These define the coding standard.
- **Type Checking Config:** `mypy.ini`, `pyrightconfig.json`.
- **Testing Framework:** Look for a `tests/` directory, `pytest.ini`, or `tox.ini` to identify `pytest`, `unittest`, etc.

## 2. Core Principles

- **Style:** Strictly adhere to the project's configured linter (e.g., `ruff`, `flake8`) and formatter (e.g., `black`, `autopep8`). If none exist, default to PEP 8.
- **Type Hints:** If the project uses type hints, you MUST use them for all new code. Match the existing style.
- **Imports:** Follow the project's import organization (e.g., stdlib, third-party, local). Use the configured import sorter (like `isort`).
- **Docstrings:** Match the existing docstring format (e.g., Google, NumPy, reStructuredText).

## 3. Dependency Management

- **`pip`:** If the project uses `requirements.txt`, add new dependencies to the file and then run `pip install -r requirements.txt`.
- **`poetry`:** If the project uses `pyproject.toml` with poetry, add new dependencies using `poetry add <package-name>` and install them with `poetry install`.

## 4. Implementation Patterns

- **Error Handling:** Replicate the existing patterns for exceptions, logging, and error wrapping.
- **Testing:** Use the project's existing test structure, fixtures, and mocking libraries. Add tests for all new code.
- **Debugging:** Use the built-in `pdb` for debugging, or `ipdb` if it's available in the project.

## 5. Project Structure

- **Simple scripts:** For single-file scripts, keep them in the root of the project.
- **Larger projects:** For larger projects, use a `src` layout, where the main source code resides in a `src` directory. Tests should be in a separate `tests` directory.

## 6. Common Commands

- **Formatting:** `black .`, `autopep8 .`
- **Linting:** `ruff check .`, `flake8 .`, `pylint .`
- **Type Checking:** `mypy .`, `pyright .`
- **Testing:** `pytest`, `python -m unittest discover`