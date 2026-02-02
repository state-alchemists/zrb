# Testing Agent - AGENTS.md

> Agent configuration for testing-related tasks in ZRB project.

---

## 🎯 Purpose

This agent specializes in software testing tasks including:
- Writing unit tests
- Writing integration tests
- Test coverage analysis
- Bug reproduction
- Test documentation
- Test strategy planning

---

## 🔧 Tools & Capabilities

### Primary Tools

```python
from zrb.llm.tool.code import analyze_code
from zrb.llm.tool.file import write_file
from zrb.llm.tool.bash import bash
```

### Available Actions

1. **analyze_code**: Analyze code for test coverage gaps
2. **write_file**: Write test files
3. **bash**: Run tests, generate coverage reports
4. **sub_agent**: Delegate testing sub-tasks

---

## 📋 Testing Tasks

### 1. Generate Unit Tests

Generate comprehensive unit tests for a module.

**Prompt Template:**
```
Analyze {file_path} and generate comprehensive unit tests:

Requirements:
1. Use pytest framework
2. Test all public functions and methods
3. Include positive and negative test cases
4. Test edge cases and error conditions
5. Use mocking for external dependencies
6. Follow Arrange-Act-Assert pattern
7. Target 90%+ code coverage

Generate tests and save to tests/test_{module_name}.py
```

**Example Task:**
```python
from zrb import LLMTask, StrInput
from zrb.llm.tool.code import analyze_code
from zrb.llm.tool.file import write_file

generate_unit_tests = LLMTask(
    name="generate-unit-tests",
    description="Generate unit tests for a module",
    input=[
        StrInput(name="target_file", description="File to test"),
        StrInput(name="output_dir", default="tests", description="Test output directory"),
    ],
    message="""
    Analyze {ctx.input.target_file} and generate comprehensive unit tests.
    
    Requirements:
    - Use pytest with pytest-asyncio for async tests
    - Test all public functions/methods
    - Include edge cases and error handling
    - Use pytest-mock for mocking
    - Follow AAA (Arrange-Act-Assert) pattern
    - Add descriptive test names
    - Target 90%+ coverage
    
    Save to appropriate location in {ctx.input.output_dir}/
    """,
    tools=[analyze_code, write_file],
)
```

### 2. Test Coverage Analysis

Analyze test coverage and identify gaps.

**Prompt Template:**
```
Run coverage analysis and generate report:

1. Execute: pytest --cov={source_dir} --cov-report=html --cov-report=term-missing
2. Identify:
   - Files with < 80% coverage
   - Uncovered lines
   - Missing edge cases
3. Generate missing tests for uncovered code
4. Save analysis to coverage_report.md
```

### 3. Integration Tests

Generate integration tests for API endpoints.

**Prompt Template:**
```
Analyze {app_file} (FastAPI app) and generate integration tests:

1. Test all API endpoints
2. Test request/response schemas
3. Test authentication flows
4. Test error responses
5. Use TestClient from FastAPI
6. Setup/teardown test database

Save to tests/integration/test_api.py
```

### 4. Bug Reproduction

Create reproduction test for a bug.

**Prompt Template:**
```
Given bug report:
{bug_description}

Create a minimal test case that:
1. Reproduces the bug consistently
2. Can be used to verify the fix
3. Will become a regression test

Save to tests/regression/test_issue_{issue_number}.py
```

---

## 🧪 Testing Standards

### Test File Structure

```python
"""Tests for module_name.

This module tests the functionality of module_name.
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock

from module import function_to_test


class TestClassName:
    """Test suite for ClassName."""
    
    def setup_method(self):
        """Setup for each test method."""
        pass
    
    def teardown_method(self):
        """Cleanup after each test method."""
        pass
    
    def test_method_name_success(self):
        """Test method_name with valid input."""
        # Arrange
        input_data = "valid_input"
        expected = "expected_output"
        
        # Act
        result = function_to_test(input_data)
        
        # Assert
        assert result == expected
    
    def test_method_name_error(self):
        """Test method_name raises error on invalid input."""
        # Arrange
        invalid_input = None
        
        # Act & Assert
        with pytest.raises(ValueError, match="expected error message"):
            function_to_test(invalid_input)


# Async tests
@pytest.mark.asyncio
class TestAsyncClass:
    """Test suite for async functionality."""
    
    async def test_async_method(self):
        """Test async method."""
        # Arrange
        mock_dep = AsyncMock()
        
        # Act
        result = await async_function(mock_dep)
        
        # Assert
        assert result is not None
```

### Naming Conventions

- **Test files**: `test_*.py` or `*_test.py`
- **Test classes**: `Test*` (e.g., `TestUserService`)
- **Test methods**: `test_*` with descriptive names
  - `test_function_name_scenario`
  - `test_method_name_success`
  - `test_method_name_raises_error`

### Fixtures

```python
import pytest


@pytest.fixture
def sample_data():
    """Provide sample test data."""
    return {"key": "value"}


@pytest.fixture
async def async_client():
    """Provide async test client."""
    from httpx import AsyncClient
    from main import app
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client


@pytest.fixture(autouse=True)
def setup_env(monkeypatch):
    """Automatically set environment for all tests."""
    monkeypatch.setenv("TEST_MODE", "true")
```

### Mocking Guidelines

```python
from unittest.mock import Mock, patch, MagicMock, AsyncMock


def test_with_mock():
    """Example of proper mocking."""
    # Mock a function
    with patch('module.external_function') as mock_func:
        mock_func.return_value = "mocked"
        result = function_under_test()
        mock_func.assert_called_once_with(expected_args)
    
    # Mock an object
    mock_obj = Mock()
    mock_obj.method.return_value = 42
    mock_obj.other.side_effect = [1, 2, 3]  # Returns 1, then 2, then 3
    
    # Async mock
    async_mock = AsyncMock()
    async_mock.async_method.return_value = "async_result"
```

---

## 📊 Coverage Requirements

### Minimum Coverage Thresholds

| Module Type | Minimum Coverage |
|-------------|------------------|
| Core functionality | 95% |
| Business logic | 90% |
| API endpoints | 85% |
| Utilities | 80% |
| Template files | 50% |

### Coverage Commands

```bash
# Generate coverage report
pytest --cov=src/zrb --cov-report=html --cov-report=term-missing

# Check coverage threshold
pytest --cov=src/zrb --cov-fail-under=80

# Coverage for specific module
pytest --cov=src/zrb/llm --cov-report=term-missing tests/llm/
```

---

## 🔍 Test Categories

### 1. Unit Tests

```python
# tests/unit/test_task.py
def test_task_execution():
    """Test basic task execution."""
    task = Task(name="test", action=lambda ctx: "result")
    result = asyncio.run(task.run())
    assert result == "result"
```

### 2. Integration Tests

```python
# tests/integration/test_cli.py
def test_cli_command():
    """Test CLI command execution."""
    runner = CliRunner()
    result = runner.invoke(cli, ['task', 'run'])
    assert result.exit_code == 0
    assert "success" in result.output
```

### 3. Property-Based Tests

```python
# Using hypothesis for property-based testing
from hypothesis import given, strategies as st

@given(st.lists(st.integers()))
def test_sort_idempotent(data):
    """Sorting twice should give same result as sorting once."""
    assert sorted(sorted(data)) == sorted(data)
```

---

## 🔄 Testing Workflow

### Pre-commit Testing

```python
from zrb import cli, Group, CmdTask

test_group = cli.add_group(Group(name="test", description="🧪 Testing tasks"))

# Run all tests
run_tests = test_group.add_task(CmdTask(
    name="all",
    description="Run all tests with coverage",
    cmd="pytest --cov=src/zrb --cov-report=term-missing -v",
))

# Run unit tests only
run_unit = test_group.add_task(CmdTask(
    name="unit",
    description="Run unit tests",
    cmd="pytest tests/unit -v",
))

# Run integration tests
run_integration = test_group.add_task(CmdTask(
    name="integration",
    description="Run integration tests",
    cmd="pytest tests/integration -v",
))

# Generate coverage report
generate_coverage = test_group.add_task(CmdTask(
    name="coverage",
    description="Generate HTML coverage report",
    cmd="pytest --cov=src/zrb --cov-report=html && open htmlcov/index.html",
))
```

### LLM-Powered Test Generation Workflow

```python
from zrb import LLMTask, CmdTask
from zrb.llm.tool.code import analyze_code

# Step 1: Analyze code for test gaps
gap_analysis = LLMTask(
    name="analyze-test-gaps",
    description="Find untested code",
    message="""
    Run coverage report on {ctx.input.module} and identify:
    1. Untested functions
    2. Uncovered branches
    3. Missing edge cases
    """,
)

# Step 2: Generate tests for gaps
generate_missing = LLMTask(
    name="generate-missing-tests",
    description="Generate tests for uncovered code",
    tools=[analyze_code, write_file],
    message="Generate tests for the uncovered code identified...",
)

# Step 3: Validate tests
validate = CmdTask(
    name="validate-tests",
    description="Run new tests",
    cmd="pytest {ctx.input.test_file} -v",
)

gap_analysis >> generate_missing >> validate
```

---

## ✅ Testing Checklist

Before considering testing complete:

- [ ] All public APIs have tests
- [ ] Edge cases are covered
- [ ] Error conditions are tested
- [ ] Tests are independent (no shared state)
- [ ] Tests run quickly (< 10s per test)
- [ ] Coverage meets minimum threshold
- [ ] Mocks are properly configured
- [ ] Test names are descriptive
- [ ] Assertions have clear messages

---

## 🔗 Related Agents

- `../documentation/AGENTS.md` - For test documentation
- `../planning/AGENTS.md` - For test planning
- `../refactoring/AGENTS.md` - For refactoring with tests

---

*Last updated: 2026-02-02*
