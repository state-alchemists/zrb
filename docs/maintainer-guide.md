🔖 [Documentation Home](../README.md) > Maintainer Guide

# Maintainer Guide


To publish Zrb, you need a `Pypi` account:

- Log in or register to [https://pypi.org/](https://pypi.org/)
- Create an API token

You can also create a `TestPypi` account:

- Log in or register to [https://test.pypi.org/](https://test.pypi.org/)
- Create an API token

Once you have your API token, you need to configure poetry as follow:

```bash
poetry config pypi-token.pypi <your-api-token>
```


To publish Zrb, you can do the following command:

```bash
source ./project.sh
docker login -U stalchmst

zrb publish all
```

# Inspecting Import Performance

To inspect import peformance, you can run the following command:

```bash
pip install benchmark-imports
python -m benchmark_imports zrb
```

You can use the result to decide whether a module/dependency should be lazy-loaded or not.

# Testing Strategies and Mocking Techniques

The Zrb test suite employs several powerful techniques from `pytest` and `unittest.mock` to ensure code correctness and isolate components during testing. Understanding these can help in writing and maintaining tests.

## Pytest Fixtures (`@pytest.fixture`)

Fixtures are used to set up reusable test data, state, or helper objects. They provide a consistent baseline for tests and can manage setup and teardown logic.

**Purpose:**
-   Provide a fixed baseline for tests.
-   Manage setup and teardown of resources.
-   Make tests cleaner and more readable by abstracting setup logic.

**Example (`mock_os_path` from [`test/test_main.py`](../test/test_main.py:10)):**
This fixture creates a temporary directory structure and mocks several `os` and `os.path` functions. This is crucial for tests that need to simulate specific file system interactions without affecting the actual file system.

```python
# In test/test_main.py
@pytest.fixture
def mock_os_path(tmp_path):
    """Fixture to mock os.path functions within a temporary directory."""
    original_abspath = os.path.abspath
    # ... (setup of mock directory and functions) ...
    with mock.patch("os.getcwd", mock_getcwd), \
         mock.patch("os.path.abspath", mock_abspath), \
         # ... (other patches) ...
        yield tmp_path, nested_dir
    # ... (teardown, if any, though usually handled by mock context manager) ...
```
Tests can then use `mock_os_path` as an argument to get this pre-configured environment.

## Mocking with `unittest.mock.patch`

Mocking is essential for isolating the code under test from its dependencies (like external services, file system, or other modules). `unittest.mock.patch` can be used as a decorator or a context manager.

### Decorator (`@mock.patch(...)`)

**Purpose:**
-   Replaces an object with a mock for the *entire duration* of the decorated test function.
-   The mock object is passed as an argument to the test function, allowing for configuration and assertion.

**Example (from [`test/test_main.py`](../test/test_main.py:127) patching `Config.LOGGER`):**
Here, `zrb.config.Config.LOGGER` is patched for the `test_serve_cli_normal_execution` function. The `mock_logger` argument allows the test to inspect calls to the logger.

```python
# In test/test_main.py
@mock.patch("zrb.config.Config.LOGGER", new_callable=mock.MagicMock)
@mock.patch("zrb.__main__.logging.StreamHandler")
# ... other decorators ...
def test_serve_cli_normal_execution(
    # ... other mock arguments ...,
    mock_handler,
    mock_logger, # mock_logger is injected by the @mock.patch decorator
):
    # ... test logic using mock_logger ...
    mock_logger.setLevel.assert_called_once()
```

### Context Manager (`with patch(...)`)

**Purpose:**
-   Replaces an object with a mock *only within the `with` block*.
-   Useful for fine-grained control or when different mock configurations are needed within a single test.

**Example (from [`test/task/test_cmd_task.py`](../test/task/test_cmd_task.py:165) patching `Config.WARN_UNRECOMMENDED_COMMAND`):**
This test needs to check behavior with `WARN_UNRECOMMENDED_COMMAND` being `True` and then `False`. The context manager is ideal for this.

```python
# In test/task/test_cmd_task.py
from unittest.mock import patch, PropertyMock

def test_cmd_task_get_should_warn_unrecommended_commands():
    patch_target = "zrb.config.Config.WARN_UNRECOMMENDED_COMMAND"
    with patch(patch_target, new_callable=PropertyMock) as mock_warn_prop:
        mock_warn_prop.return_value = True
        task = CmdTask(name="test_warn_default_true", warn_unrecommended_command=None)
        assert task._get_should_warn_unrecommended_commands() is True

    with patch(patch_target, new_callable=PropertyMock) as mock_warn_prop:
        mock_warn_prop.return_value = False
        # ... rest of the test ...
```

**Choosing Between Decorator and Context Manager:**
-   Use decorators when the mock is needed for the entire test function or when the mock object needs to be an argument to the test.
-   Use context managers for more localized mocking or when you need to apply different patches to the same object within one test.

The key to resolving recent `AttributeError: can't delete attribute` issues was to ensure that when patching properties on the `zrb.config.CFG` object (which is an instance of `zrb.config.Config`), the patch target was the property definition on the *class* (`zrb.config.Config.PROPERTY_NAME`) rather than the instance. This is often more robust, especially when using `new_callable=PropertyMock` for properties.

🔖 [Documentation Home](../README.md)
