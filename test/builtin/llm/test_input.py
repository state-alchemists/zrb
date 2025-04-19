import os
from types import SimpleNamespace
from unittest import mock

import pytest

from zrb.builtin.llm.input import PreviousSessionInput


@pytest.fixture
def mock_shared_context():
    """Fixture for a mocked AnySharedContext."""
    context = mock.Mock()
    # Mock necessary attributes used by get_default_str if needed
    context.input = SimpleNamespace()
    context.session = SimpleNamespace()
    context.task = SimpleNamespace()
    return context


@mock.patch("zrb.builtin.llm.input.read_file")
@mock.patch(
    "zrb.builtin.llm.input.os.path.dirname"
)  # Mock dirname to control file path
def test_previous_session_input_to_html(
    mock_dirname, mock_read_file, mock_shared_context
):
    """Test the to_html method of PreviousSessionInput."""
    input_name = "prev_session"
    input_description = "Previous Session Name"
    input_default = "last_run"
    fake_dir = "/fake/dir"
    js_file_path = os.path.join(fake_dir, "previous-session.js")
    js_content = """
    console.log("Input Name: CURRENT_INPUT_NAME");
    function CurrentPascalInputName() { /* ... */ }
    """

    mock_dirname.return_value = fake_dir
    mock_read_file.return_value = js_content

    # Instantiate the input object
    prev_session_input = PreviousSessionInput(
        name=input_name, description=input_description, default=input_default
    )

    # Mock get_default_str to return the default value directly for simplicity
    with mock.patch.object(
        prev_session_input, "get_default_str", return_value=input_default
    ):
        html_output = prev_session_input.to_html(mock_shared_context)

    # Assertions
    mock_dirname.assert_called_once()
    mock_read_file.assert_called_once_with(
        file_path=js_file_path,
        replace_map={
            "CURRENT_INPUT_NAME": input_name,
            "CurrentPascalInputName": "PrevSession",  # Assuming to_pascal_case works
        },
    )

    # Check the generated HTML structure
    expected_input_tag = f'<input name="{input_name}" placeholder="{input_description}" value="{input_default}" />'
    expected_script_tag = (
        f"<script>{js_content}</script>"  # JS content is returned directly by mock
    )

    assert expected_input_tag in html_output
    assert expected_script_tag in html_output
    assert html_output == f"{expected_input_tag}\n{expected_script_tag}"
