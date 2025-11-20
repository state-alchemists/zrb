---
description: "A workflow for developing with Python, including project analysis and best practices."
---
Follow this workflow to deliver clean, maintainable Python code that follows PEP standards and project conventions.

# Core Mandates

- **PEP 8 Compliance:** Follow Python style guide unless project specifies otherwise
- **Type Safety:** Use type hints when project supports them
- **Virtual Environments:** Always work within appropriate Python environments
- **Testing Excellence:** Write comprehensive tests for all functionality

# Tool Usage Guideline
- Use `read_from_file` to analyze pyproject.toml, requirements.txt, and source code
- Use `search_files` to find Python patterns and conventions
- Use `run_shell_command` for Python toolchain operations
- Use `list_files` to understand project structure

# Step 1: Project Analysis

1. **Dependency Management:** Examine `pyproject.toml`, `requirements.txt`, `setup.py`
2. **Virtual Environment:** Check for `.venv`, `venv`, or other environment indicators
3. **Python Version:** Look for `.python-version` or configuration in `pyproject.toml`
4. **Linting Configuration:** Check for `ruff.toml`, `.flake8`, `.pylintrc`
5. **Type Checking:** Look for `mypy.ini`, `pyrightconfig.json`
6. **Testing Framework:** Analyze `tests/` directory, `pytest.ini`, `tox.ini`

# Step 2: Environment Setup

1. **Activate Virtual Environment:**
   ```bash
   source .venv/bin/activate  # Linux/Mac
   .venv\Scripts\activate     # Windows
   ```
2. **Create Environment if Missing:**
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -e .  # Install project in development mode
   ```
3. **Install Dependencies:** Use appropriate package manager (pip, poetry, pdm)

# Step 3: Understand Conventions

1. **Code Style:** Adhere to project's configured linter (ruff, flake8, pylint)
2. **Type Hints:** Use type hints if project supports them, following existing patterns
3. **Import Organization:** Follow project's import sorting (isort, ruff)
4. **Docstring Format:** Match existing format (Google, NumPy, reStructuredText)
5. **Testing Patterns:** Follow established pytest or unittest patterns

# Step 4: Implementation Planning

1. **Module Structure:** Plan where new code should be placed
2. **Class Design:** Design classes following Pythonic principles
3. **Function Design:** Create focused, single-responsibility functions
4. **Type Annotations:** Plan appropriate type hints for new code
5. **Testing Strategy:** Plan comprehensive unit and integration tests

# Step 5: Write Code

## Code Quality Standards
- **Formatting:** Use black, autopep8, or ruff format with project configuration
- **Linting:** Address all linter warnings (ruff, flake8, pylint)
- **Type Hints:** Add comprehensive type annotations
- **Documentation:** Write clear docstrings following project format
- **Naming:** Use snake_case for variables/functions, PascalCase for classes

## Pythonic Patterns
- **List Comprehensions:** Use for simple transformations
- **Context Managers:** Use `with` statements for resource management
- **Generators:** Use for large datasets or streaming data
- **Decorators:** Use for cross-cutting concerns
- **Data Classes:** Use for simple data containers (Python 3.7+)

# Step 6: Testing and Verification

1. **Write Tests:** Create comprehensive tests using project's test framework
2. **Run Tests:** Execute `pytest` or `python -m unittest`
3. **Type Checking:** Run `mypy` or `pyright` if configured
4. **Linting:** Run `ruff check` or project's linter
5. **Formatting:** Run `black` or project's formatter

# Step 7: Quality Assurance

## Testing Standards
- **Test Organization:** Follow project's test structure and naming
- **Fixtures:** Use pytest fixtures for test setup
- **Mocking:** Use unittest.mock or pytest-mock appropriately
- **Coverage:** Aim for high test coverage of business logic
- **Parametrized Tests:** Use for testing multiple input scenarios

## Code Review Checklist
- [ ] Code follows PEP 8 and project formatting standards
- [ ] All tests pass with good coverage
- [ ] Type checking passes (if configured)
- [ ] No linter warnings
- [ ] Docstrings are complete and follow project format
- [ ] Error handling is appropriate
- [ ] Performance considerations addressed

# Step 8: Package Management

## Dependency Management
- **pip:** Add to `requirements.txt` and run `pip install -r requirements.txt`
- **poetry:** Use `poetry add <package>` and `poetry install`
- **pdm:** Use `pdm add <package>` and `pdm install`

## Common Commands
- `python -m pytest`: Run tests with pytest
- `python -m mypy .`: Run type checking with mypy
- `python -m black .`: Format code with black
- `python -m ruff check .`: Lint code with ruff
- `python -m isort .`: Sort imports with isort

# Step 9: Finalize and Deliver

1. **Verify Environment:** Ensure virtual environment is active and dependencies installed
2. **Run Full Test Suite:** Verify all existing tests still pass
3. **Static Analysis:** Address any remaining linting or type issues
4. **Documentation:** Update relevant documentation, docstrings, and README
5. **Packaging:** Verify package can be built and installed if applicable

# Advanced Python Features

## Modern Python (3.8+)
- **Walrus Operator:** Use `:=` for assignment in expressions
- **Structural Pattern Matching:** Use `match`/`case` for complex conditionals
- **Positional-only Parameters:** Use `/` in function definitions
- **Dataclasses:** Use for simple data containers

## Performance Optimization
- **Profiling:** Use cProfile for performance analysis
- **Caching:** Use functools.lru_cache for expensive function calls
- **Async/Await:** Use for I/O-bound operations
- **C Extensions:** Consider for performance-critical code

## Security Considerations
- **Input Validation:** Validate and sanitize all user inputs
- **Dependency Security:** Use tools like safety or bandit
- **Secret Management:** Never hardcode secrets in code
- **SQL Injection:** Use parameterized queries

# Risk Assessment Guidelines

## Low Risk (Proceed Directly)
- Adding tests to existing test suites
- Implementing utility functions following established patterns
- Creating new modules in established patterns

## Moderate Risk (Explain and Confirm)
- Modifying core business logic
- Changing public API interfaces
- Adding new dependencies
- Modifying virtual environment or dependency configuration

## High Risk (Refuse and Explain)
- Breaking backward compatibility
- Modifying critical security components
- Changes affecting multiple packages
- Operations that could break the virtual environment