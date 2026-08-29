"""Structured, non-sensitive diagnostics for policy decisions.

Policy diagnostics are DEBUG-only and intentionally exclude tool arguments,
credentials, prompts, and message content. They make the effective decision
and fallback path inspectable without turning the audit logger into a secret
store.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from zrb.config.config import CFG


def record_policy_decision(
    *,
    layer: str,
    decision: str,
    tool_name: str = "",
    reason: str = "",
    fallback: str = "",
) -> None:
    """Emit one structured policy event without sensitive request data."""
    event: dict[str, Any] = {
        "event": "policy_decision",
        "layer": layer,
        "decision": decision,
    }
    if tool_name:
        event["tool"] = tool_name
    if reason:
        event["reason"] = reason
    if fallback:
        event["fallback"] = fallback
    if CFG.LOGGER.isEnabledFor(logging.DEBUG):
        CFG.LOGGER.debug(json.dumps(event, sort_keys=True))


__all__ = ["record_policy_decision"]
