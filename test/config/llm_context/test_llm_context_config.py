import os
from unittest import mock

from zrb.config.llm_context.config import LLMContextConfig

# Mock data for a config file in a project directory
PROJECT_CONFIG_CONTENT = """
# Context: .
This is the project context.

# Context: ./specific
This is for a specific sub-directory.

# Workflow: test-workflow
This is a test workflow.

# Context: /tmp/global
This is a global context.
"""

# Mock data for a config file in the home directory
HOME_CONFIG_CONTENT = """
# Context: .
This is the home context.

# Workflow: global-workflow
This is a global workflow.
"""

# Mock data with nested code fences
FENCED_CONFIG_CONTENT = """
# Context: .
This context has code fences.
```python
# this is a hello function
def hello():
    print("Hello")
    ```
    And here is a nested fence:
    ```
    ```
    This is inside the nested fence.
    ```
```
# Context: ./another-project
"""

mock_files = {}


def setup_fs(files):
    global mock_files
    mock_files = files.copy()


def mock_exists_side_effect(path):
    return path in mock_files


def mock_open_side_effect(path, mode="r"):
    if mode == "r":
        if path in mock_files:
            return mock.mock_open(read_data=mock_files[path]).return_value
        raise FileNotFoundError(f"No such file or directory: '{path}'")
    elif mode == "w":
        mock_files[path] = ""

        def write_side_effect(data):
            mock_files[path] += data

        def writelines_side_effect(lines):
            mock_files[path] += "".join(lines)

        mock_file = mock.MagicMock()
        mock_file.__enter__.return_value.write.side_effect = write_side_effect
        mock_file.__enter__.return_value.writelines.side_effect = writelines_side_effect
        return mock_file
    return mock.mock_open().return_value


@mock.patch("zrb.config.llm_context.config.os")
@mock.patch("zrb.config.llm_context.config_handler.os")
@mock.patch("zrb.config.llm_context.config_handler.open", new_callable=mock.mock_open)
def test_get_contexts_cascading(mock_open, mock_handler_os, mock_config_os):
    # Setup mocks
    mock_handler_os.path.expanduser.return_value = "/home/user"
    mock_handler_os.path.abspath.side_effect = os.path.abspath
    mock_handler_os.path.join.side_effect = os.path.join
    mock_handler_os.path.dirname.side_effect = os.path.dirname
    mock_handler_os.path.relpath.side_effect = os.path.relpath
    mock_handler_os.path.exists.side_effect = mock_exists_side_effect
    mock_open.side_effect = mock_open_side_effect
    mock_config_os.getcwd.return_value = "/home/user/project"

    # Setup file system
    setup_fs(
        {
            "/home/user/ZRB.md": HOME_CONFIG_CONTENT,
            "/home/user/project/ZRB.md": PROJECT_CONFIG_CONTENT,
        }
    )

    config = LLMContextConfig()
    context = config.get_contexts()

    assert "/home/user/project" in context
    assert "/home/user" in context
    assert "This is the home context." in context["/home/user"]
    assert "This is the project context." in context["/home/user/project"]
    assert "This is the home context." not in context["/home/user/project"]


@mock.patch("zrb.config.llm_context.config.os")
@mock.patch("zrb.config.llm_context.config_handler.os")
@mock.patch("zrb.config.llm_context.config_handler.open", new_callable=mock.mock_open)
def test_get_contexts_with_absolute_path_and_fenced_code(
    mock_open, mock_handler_os, mock_config_os
):
    mock_handler_os.path.expanduser.return_value = "/home/user"
    mock_handler_os.path.abspath.side_effect = os.path.abspath
    mock_handler_os.path.join.side_effect = os.path.join
    mock_handler_os.path.dirname.side_effect = os.path.dirname
    mock_handler_os.path.relpath.side_effect = os.path.relpath
    mock_handler_os.path.isabs.side_effect = os.path.isabs
    mock_handler_os.path.exists.side_effect = mock_exists_side_effect
    mock_open.side_effect = mock_open_side_effect
    mock_config_os.getcwd.return_value = "/home/user/project"

    setup_fs(
        {
            "/home/user/project/ZRB.md": FENCED_CONFIG_CONTENT,
            "/home/user/ZRB.md": PROJECT_CONFIG_CONTENT,
        }
    )

    config = LLMContextConfig()
    context = config.get_contexts()

    assert "/tmp/global" in context
    assert context["/tmp/global"] == "This is a global context."
    assert "This context has code fences." in context["/home/user/project"]
    assert "# this is a hello function" in context["/home/user/project"]
    assert "def hello()" in context["/home/user/project"]
    assert "# Context: ./another-project" not in context["/home/user/project"]


@mock.patch("zrb.config.llm_context.config.os")
@mock.patch("zrb.config.llm_context.config_handler.os")
@mock.patch("zrb.config.llm_context.config_handler.open", new_callable=mock.mock_open)
def test_get_workflows(mock_open, mock_handler_os, mock_config_os):
    mock_handler_os.path.expanduser.return_value = "/home/user"
    mock_handler_os.path.abspath.side_effect = os.path.abspath
    mock_handler_os.path.join.side_effect = os.path.join
    mock_handler_os.path.dirname.side_effect = os.path.dirname
    mock_handler_os.path.exists.side_effect = mock_exists_side_effect
    mock_open.side_effect = mock_open_side_effect
    mock_config_os.getcwd.return_value = "/home/user/project"

    setup_fs(
        {
            "/home/user/ZRB.md": HOME_CONFIG_CONTENT,
            "/home/user/project/ZRB.md": PROJECT_CONFIG_CONTENT,
        }
    )

    config = LLMContextConfig()
    workflows = config.get_workflows()

    assert "global-workflow" in workflows
    assert "test-workflow" in workflows
    assert workflows["global-workflow"] == "This is a global workflow."


@mock.patch("zrb.config.llm_context.config.os")
@mock.patch("zrb.config.llm_context.config_handler.os")
@mock.patch("zrb.config.llm_context.config_handler.open", new_callable=mock.mock_open)
def test_add_to_context_new_file(mock_open, mock_handler_os, mock_config_os):
    mock_handler_os.path.expanduser.return_value = "/home/user"
    mock_handler_os.path.abspath.side_effect = os.path.abspath
    mock_handler_os.path.join.side_effect = os.path.join
    mock_handler_os.path.dirname.side_effect = os.path.dirname
    mock_handler_os.path.relpath.side_effect = os.path.relpath
    mock_handler_os.path.exists.side_effect = mock_exists_side_effect
    mock_open.side_effect = mock_open_side_effect
    mock_config_os.getcwd.return_value = "/home/user/project"
    mock_config_os.path.abspath.side_effect = os.path.abspath
    mock_config_os.path.expanduser.return_value = "/home/user"

    setup_fs({})

    config = LLMContextConfig()
    config.add_to_context("New content.")

    assert "/home/user/ZRB.md" in mock_files
    assert "# Context: ./project" in mock_files["/home/user/ZRB.md"]
    assert "New content." in mock_files["/home/user/ZRB.md"]


@mock.patch("zrb.config.llm_context.config.os")
@mock.patch("zrb.config.llm_context.config_handler.os")
@mock.patch("zrb.config.llm_context.config_handler.open", new_callable=mock.mock_open)
def test_add_to_context_new_file_global(mock_open, mock_handler_os, mock_config_os):
    mock_handler_os.path.expanduser.return_value = "/home/user"
    mock_handler_os.path.abspath.side_effect = os.path.abspath
    mock_handler_os.path.join.side_effect = os.path.join
    mock_handler_os.path.dirname.side_effect = os.path.dirname
    mock_handler_os.path.relpath.side_effect = os.path.relpath
    mock_handler_os.path.isabs.side_effect = os.path.isabs
    mock_handler_os.path.exists.side_effect = mock_exists_side_effect
    mock_open.side_effect = mock_open_side_effect
    mock_config_os.getcwd.return_value = "/home/user/project"
    mock_config_os.path.abspath.side_effect = os.path.abspath
    mock_config_os.path.expanduser.return_value = "/home/user"

    setup_fs({})

    config = LLMContextConfig()
    config.add_to_context("Global content.", context_path="/tmp/global")

    assert "/home/user/ZRB.md" in mock_files
    assert "# Context: /tmp/global" in mock_files["/home/user/ZRB.md"]
    assert "Global content." in mock_files["/home/user/ZRB.md"]


@mock.patch("zrb.config.llm_context.config.os")
@mock.patch("zrb.config.llm_context.config_handler.os")
@mock.patch("zrb.config.llm_context.config_handler.open", new_callable=mock.mock_open)
def test_remove_from_context(mock_open, mock_handler_os, mock_config_os):
    mock_handler_os.path.expanduser.return_value = "/home/user"
    mock_handler_os.path.abspath.side_effect = os.path.abspath
    mock_handler_os.path.join.side_effect = os.path.join
    mock_handler_os.path.dirname.side_effect = os.path.dirname
    mock_handler_os.path.relpath.side_effect = os.path.relpath
    mock_handler_os.path.isabs.side_effect = os.path.isabs
    mock_handler_os.path.exists.side_effect = mock_exists_side_effect
    mock_open.side_effect = mock_open_side_effect
    mock_config_os.getcwd.return_value = "/home/user/project"
    mock_config_os.path.abspath.side_effect = os.path.abspath
    mock_config_os.path.expanduser.return_value = "/home/user"

    setup_fs({"/home/user/ZRB.md": ("# Context: .\n" "Line 1\n" "Line 2\n" "Line 3\n")})

    config = LLMContextConfig()
    was_removed = config.remove_from_context("Line 2", context_path="/home/user")
    assert was_removed
    assert "Line 1" in mock_files["/home/user/ZRB.md"]
    assert "Line 2" not in mock_files["/home/user/ZRB.md"]
    assert "Line 3" in mock_files["/home/user/ZRB.md"]

    was_removed_again = config.remove_from_context(
        "Non-existent", context_path="/home/user"
    )
    assert not was_removed_again
