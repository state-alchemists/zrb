import os
from unittest.mock import patch

from zrb.builtin.llm.tool.note import (
    read_contextual_note,
    read_long_term_note,
    write_contextual_note,
    write_long_term_note,
)

MOCK_NOTE_DIR = os.path.join(os.path.expanduser("~"), ".zrb_test", "llm_context")
MOCK_CONFIG_FILE = os.path.join(MOCK_NOTE_DIR, "context.md")


def setup_function(function):
    os.makedirs(MOCK_NOTE_DIR, exist_ok=True)
    if os.path.exists(MOCK_CONFIG_FILE):
        os.remove(MOCK_CONFIG_FILE)


def teardown_function(function):
    if os.path.exists(MOCK_CONFIG_FILE):
        os.remove(MOCK_CONFIG_FILE)


@patch(
    "zrb.config.llm_context.config.llm_context_config._get_home_config_file",
    return_value=MOCK_CONFIG_FILE,
)
def test_long_term_note(mock_get_home_config_file):
    assert read_long_term_note() == ""
    write_long_term_note("hello")
    assert read_long_term_note() == "hello"


@patch(
    "zrb.config.llm_context.config.llm_context_config._get_home_config_file",
    return_value=MOCK_CONFIG_FILE,
)
def test_contextual_note(mock_get_home_config_file):
    assert read_contextual_note("foo") == ""
    write_contextual_note("bar", "foo")
    assert read_contextual_note("foo") == "bar"
    write_contextual_note("baz")
    assert read_contextual_note() == "baz"
    assert read_contextual_note(os.getcwd()) == "baz"
