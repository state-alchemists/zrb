"""Characterization tests for pipeline_refactored.py.

Locks down the observable behavior of the ETL pipeline so regressions
are caught during future refactoring.
"""

import sqlite3
import textwrap
from pathlib import Path

import pytest

from pipeline_refactored import (
    Config,
    ErrorEvent,
    UserEvent,
    ApiCall,
    WarnEvent,
    ParsedLog,
    aggregate_errors,
    compute_endpoint_latency,
    count_active_sessions,
    extract_log_events,
    generate_report,
    parse_log_line,
    persist_to_db,
    run_pipeline,
    write_report,
)


# ---------------------------------------------------------------------------
# parse_log_line
# ---------------------------------------------------------------------------


class TestParseLogLine:
    """Tests for individual log-line parsing."""

    def should_parse_error_line(self) -> None:
        result = parse_log_line("2024-01-01 12:05:00 ERROR Database timeout\n")
        assert result == ErrorEvent(timestamp="2024-01-01 12:05:00", message="Database timeout")

    def should_parse_warn_line(self) -> None:
        result = parse_log_line("2024-01-01 12:09:00 WARN Memory usage at 87%\n")
        assert result == WarnEvent(timestamp="2024-01-01 12:09:00", message="Memory usage at 87%")

    def should_parse_user_login(self) -> None:
        result = parse_log_line("2024-01-01 12:00:00 INFO User 42 logged in\n")
        assert result == UserEvent(timestamp="2024-01-01 12:00:00", user_id="42", action="logged in")

    def should_parse_user_logout(self) -> None:
        result = parse_log_line("2024-01-01 12:10:00 INFO User 42 logged out\n")
        assert result == UserEvent(timestamp="2024-01-01 12:10:00", user_id="42", action="logged out")

    def should_parse_api_call(self) -> None:
        result = parse_log_line("2024-01-01 12:08:00 INFO API /users/profile took 250ms\n")
        assert result == ApiCall(timestamp="2024-01-01 12:08:00", endpoint="/users/profile", latency_ms=250)

    def should_parse_api_call_without_latency(self) -> None:
        result = parse_log_line("2024-01-01 12:08:00 INFO API /health\n")
        assert result == ApiCall(timestamp="2024-01-01 12:08:00", endpoint="/health", latency_ms=0)

    def should_return_none_for_malformed_line(self) -> None:
        assert parse_log_line("garbage line") is None

    def should_return_none_for_unknown_level(self) -> None:
        assert parse_log_line("2024-01-01 12:00:00 DEBUG something\n") is None


# ---------------------------------------------------------------------------
# extract_log_events
# ---------------------------------------------------------------------------


class TestExtractLogEvents:
    """Tests for full log-file extraction."""

    def should_parse_sample_log(self, tmp_path: Path) -> None:
        log = tmp_path / "server.log"
        log.write_text(textwrap.dedent("""\
            2024-01-01 12:00:00 INFO User 42 logged in
            2024-01-01 12:05:00 ERROR Database timeout
            2024-01-01 12:05:05 ERROR Database timeout
            2024-01-01 12:08:00 INFO API /users/profile took 250ms
            2024-01-01 12:09:00 WARN Memory usage at 87%
            2024-01-01 12:10:00 INFO User 42 logged out
        """))
        parsed = extract_log_events(log)
        assert len(parsed.errors) == 2
        assert len(parsed.api_calls) == 1
        assert len(parsed.user_events) == 2
        assert len(parsed.warnings) == 1

    def should_raise_on_missing_file(self) -> None:
        with pytest.raises(FileNotFoundError):
            extract_log_events(Path("/nonexistent/server.log"))


# ---------------------------------------------------------------------------
# Transform functions
# ---------------------------------------------------------------------------


class TestAggregateErrors:
    def should_count_duplicate_errors(self) -> None:
        errors = [
            ErrorEvent("2024-01-01 12:00:00", "Database timeout"),
            ErrorEvent("2024-01-01 12:00:01", "Database timeout"),
            ErrorEvent("2024-01-01 12:00:02", "Disk full"),
        ]
        result = aggregate_errors(errors)
        assert result == {"Database timeout": 2, "Disk full": 1}

    def should_return_empty_for_no_errors(self) -> None:
        assert aggregate_errors([]) == {}


class TestComputeEndpointLatency:
    def should_average_latencies(self) -> None:
        calls = [
            ApiCall("2024-01-01 12:00:00", "/users", 100),
            ApiCall("2024-01-01 12:01:00", "/users", 200),
        ]
        result = compute_endpoint_latency(calls)
        assert result == {"/users": 150.0}

    def should_return_empty_for_no_calls(self) -> None:
        assert compute_endpoint_latency([]) == {}


class TestCountActiveSessions:
    def should_count_active_users(self) -> None:
        events = [
            UserEvent("2024-01-01 12:00:00", "42", "logged in"),
            UserEvent("2024-01-01 12:00:01", "99", "logged in"),
        ]
        assert count_active_sessions(events) == 2

    def should_not_count_logged_out_users(self) -> None:
        events = [
            UserEvent("2024-01-01 12:00:00", "42", "logged in"),
            UserEvent("2024-01-01 12:01:00", "42", "logged out"),
            UserEvent("2024-01-01 12:00:01", "99", "logged in"),
        ]
        assert count_active_sessions(events) == 1

    def should_return_zero_for_no_events(self) -> None:
        assert count_active_sessions([]) == 0


# ---------------------------------------------------------------------------
# HTML report generation
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def should_include_error_summary(self) -> None:
        html = generate_report({"Database timeout": 2}, {}, 0)
        assert "<b>Database timeout</b>: 2 occurrences</li>" in html

    def should_include_api_latency(self) -> None:
        html = generate_report({}, {"/users/profile": 250.0}, 0)
        assert "<td>/users/profile</td><td>250.0</td>" in html

    def should_include_active_sessions(self) -> None:
        html = generate_report({}, {}, 3)
        assert "3 user(s) currently active</p>" in html


# ---------------------------------------------------------------------------
# Database persistence
# ---------------------------------------------------------------------------


class TestPersistToDb:
    def should_insert_error_and_api_rows(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        persist_to_db(db_path, {"Database timeout": 2}, {"/users": 150.0})

        conn = sqlite3.connect(db_path)
        errors = conn.execute("SELECT message, count FROM errors").fetchall()
        api = conn.execute("SELECT endpoint, avg_ms FROM api_metrics").fetchall()
        conn.close()

        assert errors == [("Database timeout", 2)]
        assert api == [("/users", 150.0)]

    def should_use_parameterized_queries_safely(self, tmp_path: Path) -> None:
        """Verify that SQL injection is not possible."""
        db_path = tmp_path / "test.db"
        malicious = "'); DROP TABLE errors; --"
        persist_to_db(db_path, {malicious: 1}, {})

        conn = sqlite3.connect(db_path)
        errors = conn.execute("SELECT message FROM errors").fetchall()
        conn.close()

        # The malicious string should be stored as data, not executed as SQL
        assert errors == [(malicious,)]


# ---------------------------------------------------------------------------
# End-to-end pipeline
# ---------------------------------------------------------------------------


class TestRunPipeline:
    def should_produce_complete_report(self, tmp_path: Path) -> None:
        log_path = tmp_path / "server.log"
        db_path = tmp_path / "metrics.db"
        report_path = tmp_path / "report.html"

        log_path.write_text(textwrap.dedent("""\
            2024-01-01 12:00:00 INFO User 42 logged in
            2024-01-01 12:05:00 ERROR Database timeout
            2024-01-01 12:05:05 ERROR Database timeout
            2024-01-01 12:08:00 INFO API /users/profile took 250ms
            2024-01-01 12:09:00 WARN Memory usage at 87%
            2024-01-01 12:10:00 INFO User 42 logged out
        """))

        cfg = Config(
            log_file=log_path,
            db_path=db_path,
            db_host="localhost",
            db_port=5432,
            db_user="admin",
            db_pass="password123",
            report_path=report_path,
        )
        run_pipeline(cfg)

        html = report_path.read_text()
        assert "<b>Database timeout</b>: 2 occurrences</li>" in html
        assert "<td>/users/profile</td><td>250.0</td>" in html
        assert "0 user(s) currently active</p>" in html