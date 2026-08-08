"""Tests for `UICommands`, the slash-command alias override object."""

from dataclasses import fields

import pytest

from zrb.llm.task.chat.ui_commands import UI_COMMAND_CFG_ATTRS, UICommands


def test_fields_match_the_configured_commands():
    """The dataclass and the CFG map describe the same command set.

    They are two views of one list. If they drift, a command either has no way
    to be overridden or overrides a default that does not exist.
    """
    # Arrange / Act
    field_names = {field.name for field in fields(UICommands)}
    # Assert
    assert field_names == set(UI_COMMAND_CFG_ATTRS), (
        "UICommands fields and UI_COMMAND_CFG_ATTRS keys have drifted: "
        f"only in dataclass={sorted(field_names - set(UI_COMMAND_CFG_ATTRS))}, "
        f"only in CFG map={sorted(set(UI_COMMAND_CFG_ATTRS) - field_names)}"
    )


def test_unset_commands_are_omitted_so_defaults_survive():
    # Arrange
    commands = UICommands(exit="/quit")
    # Act
    overrides = commands.to_overrides()
    # Assert
    assert overrides == {"exit": ["/quit"]}


def test_a_bare_string_becomes_a_single_alias():
    # Arrange
    commands = UICommands(save="/w")
    # Act
    overrides = commands.to_overrides()
    # Assert
    assert overrides["save"] == ["/w"]


def test_a_list_is_preserved_in_order():
    # Arrange
    commands = UICommands(save=["/save", "/w", "/store"])
    # Act
    overrides = commands.to_overrides()
    # Assert
    assert overrides["save"] == ["/save", "/w", "/store"]


def test_an_empty_list_is_dropped_rather_than_disabling_the_command():
    """An empty list is not an override, so the configured default applies.

    Emitting `{"exit": []}` would leave the command with no alias at all,
    silently making it unreachable.
    """
    # Arrange
    commands = UICommands(exit=[])
    # Act
    overrides = commands.to_overrides()
    # Assert
    assert "exit" not in overrides


def test_the_returned_list_does_not_alias_the_caller_s_list():
    # Arrange
    aliases = ["/save"]
    commands = UICommands(save=aliases)
    # Act
    overrides = commands.to_overrides()
    aliases.append("/mutated")
    # Assert
    assert overrides["save"] == ["/save"]


def test_a_misspelled_command_is_rejected_at_construction():
    # Arrange / Act / Assert
    with pytest.raises(TypeError, match="exitt"):
        UICommands(exitt="/quit")  # pyright: ignore[reportCallIssue]


def test_no_overrides_yields_an_empty_mapping():
    # Arrange / Act / Assert
    assert UICommands().to_overrides() == {}
