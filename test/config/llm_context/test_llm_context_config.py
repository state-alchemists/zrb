import os
from unittest import mock

from zrb.config.config import CFG
from zrb.config.llm_context.config import LLMContextConfig

# Mock data for a config file in a project directory
PROJECT_CONFIG_CONTENT = """
# Note: .
This is the project context.

# Note: ./specific
This is for a specific sub-directory.

# Workflow: test-workflow
This is a test workflow.

# Note: /tmp/global
This is a global context.
"""

# Mock data for a config file in the home directory
HOME_CONFIG_CONTENT = """
# Note: .
This is the home context.

# Workflow: global-workflow
This is a global workflow.
"""

# Mock data with nested code fences
FENCED_CONFIG_CONTENT = """
# Note: .
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
# Note: ./another-project
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
def test_get_note_and_workflow(mock_config_os, mock_open):
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
    home_config_path = f"/home/user/{CFG.LLM_CONTEXT_FILE}"
    coba_config_path = f"/home/user/coba/{CFG.LLM_CONTEXT_FILE}"
    setup_fs(
        {
            home_config_path: (
                "# Note: coba\n\n"
                "some context\n\n"
                "# Workflow: fiction-writing\n\n"
                "write fiction\n"
            ),
            coba_config_path: "# Note: .\n\noverride context\n",
        }
    )

    config = LLMContextConfig()
    contexts = config.get_notes()
    workflows = config.get_workflows()

    assert contexts == {
        "/home/user/coba": "some context",
    }
    assert "fiction-writing" in workflows
    assert workflows["fiction-writing"].name == "fiction-writing"
    assert workflows["fiction-writing"].content == "write fiction"
    assert workflows["fiction-writing"].path == "/home/user"


@mock.patch("zrb.config.llm_context.config.open", new_callable=mock.mock_open)
@mock.patch("zrb.config.llm_context.config.os")
def test_get_notes_no_cascading(mock_config_os, mock_open):
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
    home_config_path = f"/home/user/{CFG.LLM_CONTEXT_FILE}"
    project_config_path = f"/home/user/project/{CFG.LLM_CONTEXT_FILE}"
    setup_fs(
        {
            home_config_path: HOME_CONFIG_CONTENT,
            project_config_path: PROJECT_CONFIG_CONTENT,
        }
    )

    config = LLMContextConfig()
    context = config.get_notes()

    assert "/home/user" in context
    assert "This is the home context." in context["/home/user"]
    # Project context should not be loaded
    assert "/home/user/project" not in context


@mock.patch("zrb.config.llm_context.config.open", new_callable=mock.mock_open)
@mock.patch("zrb.config.llm_context.config.os")
def test_get_notes_from_home_config_only(mock_config_os, mock_open):
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

    home_config_path = f"/home/user/{CFG.LLM_CONTEXT_FILE}"
    project_config_path = f"/home/user/project/{CFG.LLM_CONTEXT_FILE}"
    setup_fs(
        {
            project_config_path: FENCED_CONFIG_CONTENT,
            home_config_path: PROJECT_CONFIG_CONTENT,
        }
    )

    config = LLMContextConfig()
    context = config.get_notes()

    # Only home config is read.
    # Fenced content from project config should not be present.
    assert "This context has code fences." not in str(context.values())

    # From home config (PROJECT_CONFIG_CONTENT):
    # "Note: ." is relative to /home/user, so it's for /home/user.
    # It is an ancestor of cwd (/home/user/project), so it's included.
    assert "/home/user" in context
    assert context["/home/user"] == "This is the project context."

    # "Note: ./specific" is for /home/user/specific, not an ancestor.
    assert "/home/user/specific" not in context

    # "Note: /tmp/global" is not an ancestor.
    assert "/tmp/global" not in context

    # There is no context for /home/user/project in the home config.
    assert "/home/user/project" not in context


@mock.patch("zrb.config.llm_context.config.open", new_callable=mock.mock_open)
@mock.patch("zrb.config.llm_context.config.os")
def test_get_notes_with_tilde_path(mock_config_os, mock_open):
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
    home_config_path = f"/home/user/{CFG.LLM_CONTEXT_FILE}"
    setup_fs({home_config_path: "# Note: ~/project\nHome config for project"})
    config = LLMContextConfig()
    contexts = config.get_notes()
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

    home_config_path = f"/home/user/{CFG.LLM_CONTEXT_FILE}"
    project_config_path = f"/home/user/project/{CFG.LLM_CONTEXT_FILE}"
    setup_fs(
        {
            home_config_path: ("# Workflow: coding\n" "Global coding workflow"),
            project_config_path: (
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
    assert workflows["coding"].content == "Project coding workflow"
    assert workflows["coding"].path == "/home/user/project"
    assert workflows["testing"].content == "Project testing workflow"
    assert workflows["testing"].path == "/home/user/project"


@mock.patch("zrb.config.llm_context.config.open", new_callable=mock.mock_open)
@mock.patch("zrb.config.llm_context.config.os")
def test_write_note_new_file(mock_config_os, mock_open):
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
    config.write_note("New content.")

    home_config_path = f"/home/user/{CFG.LLM_CONTEXT_FILE}"
    assert home_config_path in mock_files
    assert "# Note: project" in mock_files[home_config_path]
    assert "New content." in mock_files[home_config_path]


@mock.patch("zrb.config.llm_context.config.open", new_callable=mock.mock_open)
@mock.patch("zrb.config.llm_context.config.os")
def test_write_note_new_file_global(mock_config_os, mock_open):
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
    config.write_note("Global content.", context_path="/tmp/global")

    home_config_path = f"/home/user/{CFG.LLM_CONTEXT_FILE}"
    assert home_config_path in mock_files
    assert "# Note: /tmp/global" in mock_files[home_config_path]
    assert "Global content." in mock_files[home_config_path]


@mock.patch("zrb.config.llm_context.config.open", new_callable=mock.mock_open)
@mock.patch("zrb.config.llm_context.config.os")
def test_write_note_home_relative_path(mock_config_os, mock_open):
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
    config.write_note("Some docs", context_path="/home/user/docs")

    home_config_path = f"/home/user/{CFG.LLM_CONTEXT_FILE}"
    assert home_config_path in mock_files
    assert "# Note: docs" in mock_files[home_config_path]
    assert "Some docs" in mock_files[home_config_path]


@mock.patch("zrb.config.llm_context.config.open", new_callable=mock.mock_open)
@mock.patch("zrb.config.llm_context.config.os")
def test_write_note_overwrites_existing_section(mock_config_os, mock_open):
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

    home_config_path = f"/home/user/{CFG.LLM_CONTEXT_FILE}"
    file_content = (
        "# Note: project\n"
        "Original content\n"
        "\n"
        "# Workflow: test\n"
        "A workflow\n"
        "\n"
        "# Note: another_project\n"
        "Some other content\n"
    )
    setup_fs({home_config_path: file_content})

    config = LLMContextConfig()
    config.write_note("Updated content", context_path="/home/user/project")

    final_content = mock_files[home_config_path]
    assert "Original content" not in final_content
    assert "Updated content" in final_content
    assert "Some other content" in final_content


@mock.patch("zrb.config.llm_context.config.open", new_callable=mock.mock_open)
@mock.patch("zrb.config.llm_context.config.os")
def test_get_contexts(mock_config_os, mock_open):
    # Setup mocks
    mock_config_os.path.expanduser.side_effect = lambda p: p.replace("~", "/home/user")
    mock_config_os.path.abspath.side_effect = os.path.abspath
    mock_config_os.path.join.side_effect = os.path.join
    mock_config_os.path.dirname.side_effect = os.path.dirname
    mock_config_os.path.exists.side_effect = mock_exists_side_effect
    mock_open.side_effect = mock_open_side_effect
    mock_config_os.getcwd.return_value = "/home/user/project/sub"

    # Setup file system
    home_config_path = f"/home/user/{CFG.LLM_CONTEXT_FILE}"
    project_config_path = f"/home/user/project/{CFG.LLM_CONTEXT_FILE}"
    sub_config_path = f"/home/user/project/sub/{CFG.LLM_CONTEXT_FILE}"
    setup_fs(
        {
            home_config_path: "# Context\n\nThis is the home context.",
            project_config_path: "# Context\n\nThis is the project context.",
            sub_config_path: "# Note: .\n\nThis is a note in sub.",
        }
    )

    config = LLMContextConfig()
    contexts = config.get_contexts()

    assert contexts == {
        "/home/user": "This is the home context.",
        "/home/user/project": "This is the project context.",
    }


@mock.patch("zrb.config.llm_context.config.open", new_callable=mock.mock_open)
@mock.patch("zrb.config.llm_context.config.os")
def test_get_notes_with_cwd(mock_config_os, mock_open):
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

    home_config_path = f"/home/user/{CFG.LLM_CONTEXT_FILE}"
    setup_fs({home_config_path: "# Note: .\nThis is the home context."})

    config = LLMContextConfig()
    notes = config.get_notes(cwd="/home/user/project")

    assert "/home/user" in notes
    assert notes["/home/user"] == "This is the home context."
    mock_config_os.getcwd.assert_not_called()


@mock.patch("zrb.config.llm_context.config.open", new_callable=mock.mock_open)
@mock.patch("zrb.config.llm_context.config.os")
def test_write_note_for_config_dir(mock_config_os, mock_open):
    mock_config_os.path.expanduser.side_effect = lambda p: p.replace("~", "/home/user")
    mock_config_os.path.abspath.side_effect = os.path.abspath
    mock_config_os.path.join.side_effect = os.path.join
    mock_config_os.path.dirname.side_effect = os.path.dirname
    mock_config_os.path.relpath.side_effect = os.path.relpath
    mock_config_os.path.exists.side_effect = mock_exists_side_effect
    mock_open.side_effect = mock_open_side_effect
    mock_config_os.getcwd.return_value = "/home/user"

    setup_fs({})

    config = LLMContextConfig()
    config.write_note("New content for home.", context_path=".")

    home_config_path = f"/home/user/{CFG.LLM_CONTEXT_FILE}"
    assert home_config_path in mock_files
    assert "# Note: ." in mock_files[home_config_path]
    assert "New content for home." in mock_files[home_config_path]
