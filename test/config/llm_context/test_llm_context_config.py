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
    elif mode in ["w", "a"]:
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


@mock.patch("zrb.config.llm_context.config.open", new_callable=mock.mock_open)
@mock.patch("zrb.config.llm_context.config.os")
def test_get_context_and_workflow(mock_config_os, mock_open):
    # Setup mocks
    mock_config_os.path.expanduser.side_effect = lambda p: p.replace("~", "/home/user")
    mock_config_os.path.abspath.side_effect = os.path.abspath
    mock_config_os.path.join.side_effect = os.path.join
    mock_config_os.path.dirname.side_effect = os.path.dirname
    mock_config_os.path.relpath.side_effect = os.path.relpath
    mock_config_os.path.isabs.side_effect = os.path.isabs
    mock_config_os.path.sep = os.path.sep
    mock_config_os.path.commonpath.side_effect = os.path.commonpath
    mock_config_os.path.exists.side_effect = mock_exists_side_effect
    mock_open.side_effect = mock_open_side_effect
    mock_config_os.getcwd.return_value = "/home/user/coba"

    # Setup file system
    setup_fs(
        {
            "/home/user/ZRB.md": (
                "# Context: coba\n\n"
                "some context\n\n"
                "# Workflow: fiction-writing\n\n"
                "write fiction\n"
            ),
            "/home/user/coba/ZRB.md": "# Context: .\n\noverride context\n",
        }
    )

    config = LLMContextConfig()
    contexts = config.get_contexts()
    workflows = config.get_workflows()

    assert contexts == {
        "/home/user/coba": "override context",
    }
    assert workflows == {
        "fiction-writing": "write fiction",
    }


@mock.patch("zrb.config.llm_context.config.open", new_callable=mock.mock_open)
@mock.patch("zrb.config.llm_context.config.os")
def test_get_contexts_cascading(mock_config_os, mock_open):
    # Setup mocks
    mock_config_os.path.expanduser.side_effect = lambda p: p.replace("~", "/home/user")
    mock_config_os.path.abspath.side_effect = os.path.abspath
    mock_config_os.path.join.side_effect = os.path.join
    mock_config_os.path.dirname.side_effect = os.path.dirname
    mock_config_os.path.relpath.side_effect = os.path.relpath
    mock_config_os.path.isabs.side_effect = os.path.isabs
    mock_config_os.path.sep = os.path.sep
    mock_config_os.path.commonpath.side_effect = os.path.commonpath
    mock_config_os.path.exists.side_effect = mock_exists_side_effect
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


@mock.patch("zrb.config.llm_context.config.open", new_callable=mock.mock_open)
@mock.patch("zrb.config.llm_context.config.os")
def test_get_contexts_with_absolute_path_and_fenced_code(mock_config_os, mock_open):
    mock_config_os.path.expanduser.side_effect = lambda p: p.replace("~", "/home/user")
    mock_config_os.path.abspath.side_effect = os.path.abspath
    mock_config_os.path.join.side_effect = os.path.join
    mock_config_os.path.dirname.side_effect = os.path.dirname
    mock_config_os.path.relpath.side_effect = os.path.relpath
    mock_config_os.path.isabs.side_effect = os.path.isabs
    mock_config_os.path.sep = os.path.sep
    mock_config_os.path.commonpath.side_effect = os.path.commonpath
    mock_config_os.path.exists.side_effect = mock_exists_side_effect
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

    assert "/tmp/global" not in context
    assert "This context has code fences." in context["/home/user/project"]
    assert "# this is a hello function" in context["/home/user/project"]
    assert "def hello()" in context["/home/user/project"]
    assert "# Context: ./another-project" not in context["/home/user/project"]


@mock.patch("zrb.config.llm_context.config.open", new_callable=mock.mock_open)
@mock.patch("zrb.config.llm_context.config.os")
def test_get_contexts_with_tilde_path(mock_config_os, mock_open):
    mock_config_os.path.expanduser.side_effect = lambda p: p.replace("~", "/home/user")
    mock_config_os.path.abspath.side_effect = os.path.abspath
    mock_config_os.path.join.side_effect = os.path.join
    mock_config_os.path.dirname.side_effect = os.path.dirname
    mock_config_os.path.relpath.side_effect = os.path.relpath
    mock_config_os.path.isabs.side_effect = os.path.isabs
    mock_config_os.path.sep = os.path.sep
    mock_config_os.path.commonpath.side_effect = os.path.commonpath
    mock_config_os.path.exists.side_effect = mock_exists_side_effect
    mock_open.side_effect = mock_open_side_effect
    mock_config_os.getcwd.return_value = "/home/user/project"
    setup_fs({"/home/user/ZRB.md": "# Context: ~/project\nHome config for project"})
    config = LLMContextConfig()
    contexts = config.get_contexts()
    assert "/home/user/project" in contexts
    assert contexts["/home/user/project"] == "Home config for project"


@mock.patch("zrb.config.llm_context.config.open", new_callable=mock.mock_open)
@mock.patch("zrb.config.llm_context.config.os")
def test_get_workflows_override(mock_config_os, mock_open):
    mock_config_os.path.expanduser.side_effect = lambda p: p.replace("~", "/home/user")
    mock_config_os.path.abspath.side_effect = os.path.abspath
    mock_config_os.path.join.side_effect = os.path.join
    mock_config_os.path.dirname.side_effect = os.path.dirname
    mock_config_os.path.exists.side_effect = mock_exists_side_effect
    mock_open.side_effect = mock_open_side_effect
    mock_config_os.getcwd.return_value = "/home/user/project"

    setup_fs(
        {
            "/home/user/ZRB.md": ("# Workflow: coding\n" "Global coding workflow"),
            "/home/user/project/ZRB.md": (
                "# Workflow: coding\n"
                "Project coding workflow\n"
                "# Workflow: testing\n"
                "Project testing workflow"
            ),
        }
    )

    config = LLMContextConfig()
    workflows = config.get_workflows()

    assert "coding" in workflows
    assert "testing" in workflows
    assert workflows["coding"] == "Project coding workflow"
    assert workflows["testing"] == "Project testing workflow"


@mock.patch("zrb.config.llm_context.config.open", new_callable=mock.mock_open)
@mock.patch("zrb.config.llm_context.config.os")
def test_write_context_new_file(mock_config_os, mock_open):
    mock_config_os.path.expanduser.side_effect = lambda p: p.replace("~", "/home/user")
    mock_config_os.path.abspath.side_effect = os.path.abspath
    mock_config_os.path.join.side_effect = os.path.join
    mock_config_os.path.dirname.side_effect = os.path.dirname
    mock_config_os.path.relpath.side_effect = os.path.relpath
    mock_config_os.path.exists.side_effect = mock_exists_side_effect
    mock_open.side_effect = mock_open_side_effect
    mock_config_os.getcwd.return_value = "/home/user/project"

    setup_fs({})

    config = LLMContextConfig()
    config.write_context("New content.")

    assert "/home/user/project/ZRB.md" in mock_files
    assert "# Context: ." in mock_files["/home/user/project/ZRB.md"]
    assert "New content." in mock_files["/home/user/project/ZRB.md"]


@mock.patch("zrb.config.llm_context.config.open", new_callable=mock.mock_open)
@mock.patch("zrb.config.llm_context.config.os")
def test_write_context_new_file_global(mock_config_os, mock_open):
    mock_config_os.path.expanduser.side_effect = lambda p: p.replace("~", "/home/user")
    mock_config_os.path.abspath.side_effect = os.path.abspath
    mock_config_os.path.join.side_effect = os.path.join
    mock_config_os.path.dirname.side_effect = os.path.dirname
    mock_config_os.path.relpath.side_effect = os.path.relpath
    mock_config_os.path.isabs.side_effect = os.path.isabs
    mock_config_os.path.sep = os.path.sep
    mock_config_os.path.commonpath.side_effect = os.path.commonpath
    mock_config_os.path.exists.side_effect = mock_exists_side_effect
    mock_open.side_effect = mock_open_side_effect
    mock_config_os.getcwd.return_value = "/home/user/project"

    setup_fs({})

    config = LLMContextConfig()
    config.write_context("Global content.", context_path="/tmp/global")

    assert "/home/user/project/ZRB.md" in mock_files
    assert "# Context: /tmp/global" in mock_files["/home/user/project/ZRB.md"]
    assert "Global content." in mock_files["/home/user/project/ZRB.md"]


@mock.patch("zrb.config.llm_context.config.open", new_callable=mock.mock_open)
@mock.patch("zrb.config.llm_context.config.os")
def test_write_context_home_relative_path(mock_config_os, mock_open):
    mock_config_os.path.expanduser.side_effect = lambda p: p.replace("~", "/home/user")
    mock_config_os.path.abspath.side_effect = os.path.abspath
    mock_config_os.path.join.side_effect = os.path.join
    mock_config_os.path.dirname.side_effect = os.path.dirname
    mock_config_os.path.relpath.side_effect = os.path.relpath
    mock_config_os.path.isabs.side_effect = os.path.isabs
    mock_config_os.path.sep = os.path.sep
    mock_config_os.path.commonpath.side_effect = os.path.commonpath
    mock_config_os.path.exists.side_effect = mock_exists_side_effect
    mock_open.side_effect = mock_open_side_effect
    mock_config_os.getcwd.return_value = "/home/user/project"

    setup_fs({})

    config = LLMContextConfig()
    config.write_context("Some docs", context_path="/home/user/docs")

    assert "/home/user/project/ZRB.md" in mock_files
    assert "# Context: ~/docs" in mock_files["/home/user/project/ZRB.md"]
    assert "Some docs" in mock_files["/home/user/project/ZRB.md"]


@mock.patch("zrb.config.llm_context.config.open", new_callable=mock.mock_open)
@mock.patch("zrb.config.llm_context.config.os")
def test_write_context_overwrites_existing_section(mock_config_os, mock_open):
    mock_config_os.path.expanduser.side_effect = lambda p: p.replace("~", "/home/user")
    mock_config_os.path.abspath.side_effect = os.path.abspath
    mock_config_os.path.join.side_effect = os.path.join
    mock_config_os.path.dirname.side_effect = os.path.dirname
    mock_config_os.path.relpath.side_effect = os.path.relpath
    mock_config_os.path.isabs.side_effect = os.path.isabs
    mock_config_os.path.sep = os.path.sep
    mock_config_os.path.commonpath.side_effect = os.path.commonpath
    mock_config_os.path.exists.side_effect = mock_exists_side_effect
    mock_open.side_effect = mock_open_side_effect
    mock_config_os.getcwd.return_value = "/home/user/project"

    file_content = (
        "# Context: .\n"
        "Original content\n"
        "\n"
        "# Context: /home/user/another_project\n"
        "Some other content\n"
    )
    setup_fs({"/home/user/project/ZRB.md": file_content})

    config = LLMContextConfig()
    config.write_context("Updated content", context_path="/home/user/project")

    final_content = mock_files["/home/user/project/ZRB.md"]
    assert "Original content" not in final_content
    assert "Updated content" in final_content
    assert "Some other content" in final_content
