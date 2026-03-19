"""Factory for creating ApprovalChannel instances from configuration.

This module provides utilities to dynamically load and instantiate
approval channels based on configuration.
"""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING

from zrb.config.config import CFG

if TYPE_CHECKING:
    from zrb.llm.approval.channel import ApprovalChannel


def load_approval_channel() -> ApprovalChannel | None:
    """Load and instantiate an approval channel from configuration.

    Reads ZRB_LLM_APPROVAL_CHANNEL_FACTORY environment variable which should
    contain a Python import path to a factory function like:
    - "my_module.get_telegram_channel"
    - "my_package.channels.get_custom_channel"

    The factory function should return an ApprovalChannel instance.

    Returns:
        ApprovalChannel instance if factory is configured, None otherwise.

    Raises:
        ImportError: If the module cannot be imported.
        AttributeError: If the factory function doesn't exist in the module.
        TypeError: If the factory doesn't return an ApprovalChannel.
    """
    factory_path = CFG.LLM_APPROVAL_CHANNEL_FACTORY
    if not factory_path:
        return None

    # Split module path and function name
    parts = factory_path.rsplit(".", 1)
    if len(parts) == 1:
        # Just a function name, assume it's in the current scope
        module_path = ""
        func_name = parts[0]
    else:
        module_path, func_name = parts

    # Import the module
    if module_path:
        module = importlib.import_module(module_path)
    else:
        # Function is in current scope - not supported
        raise ValueError(
            f"Approval channel factory must be a full module path. "
            f"Got: {factory_path}"
        )

    # Get the factory function
    if not hasattr(module, func_name):
        raise AttributeError(
            f"Module '{module_path}' has no attribute '{func_name}'. "
            f"Make sure '{func_name}' is defined in the module."
        )

    factory = getattr(module, func_name)

    # Call the factory to get the approval channel
    channel = factory()

    # Type check
    from zrb.llm.approval.channel import ApprovalChannel

    if not isinstance(channel, ApprovalChannel):
        raise TypeError(
            f"Approval channel factory '{factory_path}' returned "
            f"{type(channel).__name__}, expected ApprovalChannel instance."
        )

    return channel