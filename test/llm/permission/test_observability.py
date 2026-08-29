"""Tests for non-sensitive structured policy diagnostics."""

from zrb.llm.permission.observability import record_policy_decision


def test_policy_diagnostic_logs_structured_non_sensitive_event(caplog):
    with caplog.at_level("DEBUG"):
        record_policy_decision(
            layer="permission",
            decision="deny",
            tool_name="Shell",
            reason="policy_rule",
        )

    assert '"event": "policy_decision"' in caplog.text
    assert '"decision": "deny"' in caplog.text
    assert '"tool": "Shell"' in caplog.text
    assert "secret" not in caplog.text
