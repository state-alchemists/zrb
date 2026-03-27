"""Shared utility for editing content via text editor."""

from __future__ import annotations

import json
import os
import tempfile
from typing import TYPE_CHECKING

from zrb.config.config import CFG
from zrb.util.yaml import yaml_dump

if TYPE_CHECKING:
    from zrb.llm.tool_call.ui_protocol import UIProtocol


async def edit_content_via_editor(
    ui: "UIProtocol",
    content: dict,
    text_editor: str | None = None,
) -> dict | None:
    """Open content in a text editor and return edited content.

    Args:
        ui: The UI protocol for running interactive commands.
        content: The content to edit (will be displayed as YAML).
        text_editor: The editor to use (defaults to CFG.EDITOR).

    Returns:
        The edited content as a dict, or None if editing failed/cancelled.
    """
    editor = text_editor or CFG.EDITOR

    # Format as YAML for editing
    is_yaml_edit = True
    try:
        content_str = yaml_dump(content)
        extension = ".yaml"
    except Exception:
        # Fallback to JSON
        content_str = json.dumps(content, indent=2)
        extension = ".json"
        is_yaml_edit = False

    # Write to temp file
    with tempfile.NamedTemporaryFile(suffix=extension, mode="w+", delete=False) as tf:
        tf.write(content_str)
        tf_path = tf.name

    # Open editor
    await ui.run_interactive_command([editor, tf_path], shell=False)

    # Read back
    with open(tf_path, "r", encoding="utf-8") as tf:
        new_content_str = tf.read()
    os.remove(tf_path)

    # Check if unchanged
    if new_content_str == content_str:
        return content  # Return original content unchanged

    # Parse edited content
    try:
        if is_yaml_edit:
            import yaml

            new_content = yaml.safe_load(new_content_str)
        else:
            new_content = json.loads(new_content_str)

        if isinstance(new_content, dict):
            return new_content
        return None
    except Exception:
        return None
