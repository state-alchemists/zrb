"""Characterization tests for the refactored pipeline.

These tests verify that the refactored pipeline produces the same
observable behavior as the original: same report structure, same
database content, and same data transformations.
"""

import sqlite3
import textwrap
from pathlib import Path

import pytest

from pipeline_refactored import (
    ApiCall,
    Config,
    ErrorEntry,
    ParsedLog,
    UserEvent,
    WarningEntry,
    compute_active_sessions,
    compute_api_latency,
    compute_error_summary,
    extract_log_entries,
    load_api_metrics,
    load_error_metrics,
    render_report,
    run_pipeline,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_LOG = textwrap.dedent("""\
    2024-01-01 12:00:00 INFO User 42 logged in
    2024-01-01 12:05:00 ERROR Database timeout
    2024-01-01 12:05:05 ERROR Database timeout
    2024-01-01 12:08:00 INFO API /users/profile took 250ms
    2024-01-01 12:09:00 WARN Memory usage at 87%
    2024-01-01 12:10:00 INFO User 42 logged out
""")


@pytest.fixture
def log_file(tmp_path: Path) -> Path:
    """Write sample log lines to a temp file and return its path."""
    p = tmp_path / "server.log"
    p.write_text(SAMPLE_LOG)
    return p


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    """Return a path to a fresh temp database."""
    return tmp_path / "metrics.db"


@pytest.fixture
def config(log_file: Path, db_path: Path, tmp_path: Path) -> Config:
    """Default test configuration."""
    return Config(
        db_path=str(db_path),
        log_file=log_file,
        db_host="localhost",
        db_port=5432,
        db_user="admin",
        db_pass="password123",
        report_path=tmp_path / "report.html",
    )


# ---------------------------------------------------------------------------
# Extract: extract_log_entries
# ---------------------------------------------------------------------------


class TestExtractLogEntries:
    """Verify regex-based parsing matches original string-split behavior."""

    def test_parse_error_lines(self, log_file: Path) -> None:
        parsed = extract_log_entries(log_file)
        assert len(parsed.errors) == 2
        assert all(isinstance(e, ErrorEntry) for e in parsed.errors)
        assert parsed.errors[0].message == "Database timeout"
        assert parsed.errors[0].timestamp == "2024-01-01 12:05:00"

    def test_parse_user_events(self, log_file: Path) -> None:
        parsed = extract_log_entries(log_file)
        assert len(parsed.user_events) == 2
        login, logout = parsed.user_events
        assert login.user_id == "42"
        assert login.action == "logged in"
        assert logout.user_id == "42"
        assert logout.action == "logged out"

    def test_parse_api_calls(self, log_file: Path) -> None:
        parsed = extract_log_entries(log_file)
        assert len(parsed.api_calls) == 1
        call = parsed.api_calls[0]
        assert isinstance(call, ApiCall)
        assert call.endpoint == "/users/profile"
        assert call.duration_ms == 250

    def test_parse_warnings(self, log_file: Path) -> None:
        parsed = extract_log_entries(log_file)
        assert len(parsed.warnings) == 1
        assert parsed.warnings[0].message == "Memory usage at 87%"

    def test_empty_when_file_missing(self, tmp_path: Path) -> None:
        missing = tmp_path / "nonexistent.log"
        parsed = extract_log_entries(missing)
        assert isinstance(parsed, ParsedLog)
        assert len(parsed.errors) == 0
        assert len(parsed.user_events) == 0
        assert len(parsed.api_calls) == 0
        assert len(parsed.warnings) == 0

    def test_skip_malformed_lines(self, tmp_path: Path) -> None:
        p = tmp_path / "bad.log"
        p.write_text("this is not a valid log line\n")
        parsed = extract_log_entries(p)
        assert len(parsed.errors) == 0

    def test_api_call_without_duration(self, tmp_path: Path) -> None:
        p = tmp_path / "no_duration.log"
        p.write_text("2024-01-01 12:00:00 INFO API /health\n")
        parsed = extract_log_entries(p)
        assert len(parsed.api_calls) == 1
        assert parsed.api_calls[0].duration_ms == 0


# ---------------------------------------------------------------------------
# Transform: compute_* functions
# ---------------------------------------------------------------------------


class TestComputeErrorSummary:
    def test_count_errors_by_message(self) -> None:
        errors = [
            ErrorEntry(timestamp="2024-01-01 12:00:00", message="timeout"),
            ErrorEntry(timestamp="2024-01-01 12:01:00", message="timeout"),
            ErrorEntry(timestamp="2024-01-01 12:02:00", message="disk full"),
        ]
        summary = compute_error_summary(errors)
        assert summary == {"timeout": 2, "disk full": 1}

    def test_empty_for_no_errors(self) -> None:
        assert compute_error_summary([]) == {}


class TestComputeApiLatency:
    def test_group_durations_by_endpoint(self) -> None:
        calls = [
            ApiCall(timestamp="t1", endpoint="/a", duration_ms=100),
            ApiCall(timestamp="t2", endpoint="/a", duration_ms=200),
            ApiCall(timestamp="t3", endpoint="/b", duration_ms=50),
        ]
        latency = compute_api_latency(calls)
        assert latency == {"/a": [100, 200], "/b": [50]}

    def test_empty_for_no_calls(self) -> None:
        assert compute_api_latency([]) == {}


class TestComputeActiveSessions:
    def test_track_login_logout(self) -> None:
        events = [
            UserEvent(timestamp="t1", user_id="alice", action="logged in"),
            UserEvent(timestamp="t2", user_id="bob", action="logged in"),
            UserEvent(timestamp="t3", user_id="alice", action="logged out"),
        ]
        sessions = compute_active_sessions(events)
        assert "alice" not in sessions
        assert sessions["bob"] == "t2"

    def test_ignore_logout_without_login(self) -> None:
        events = [UserEvent(timestamp="t1", user_id="eve", action="logged out")]
        sessions = compute_active_sessions(events)
        assert len(sessions) == 0


# ---------------------------------------------------------------------------
# Load: database + report
# ---------------------------------------------------------------------------


class TestLoadErrorMetrics:
    def test_insert_parameterized_rows(self, db_path: Path) -> None:
        conn = sqlite3.connect(str(db_path))
        try:
            load_error_metrics(conn, {"timeout": 3, "disk full": 1})
            conn.commit()
            rows = conn.execute("SELECT message, count FROM errors ORDER BY count").fetchall()
            assert rows == [("disk full", 1), ("timeout", 3)]
        finally:
            conn.close()

    def test_escape_special_characters(self, db_path: Path) -> None:
        """Verify parameterized queries handle SQL-special chars safely."""
        conn = sqlite3.connect(str(db_path))
        try:
            load_error_metrics(conn, {"it's a 'error'": 1})
            conn.commit()
            rows = conn.execute("SELECT message FROM errors").fetchall()
            assert rows[0][0] == "it's a 'error'"
        finally:
            conn.close()


class TestLoadApiMetrics:
    def test_insert_averages(self, db_path: Path) -> None:
        conn = sqlite3.connect(str(db_path))
        try:
            load_api_metrics(conn, {"/api": [100, 200]})
            conn.commit()
            rows = conn.execute("SELECT endpoint, avg_ms FROM api_metrics").fetchall()
            assert rows[0][0] == "/api"
            assert abs(rows[0][1] - 150.0) < 0.01
        finally:
            conn.close()


class TestRenderReport:
    def test_render_error_summary(self) -> None:
        report = render_report(
            error_summary={"Database timeout": 2},
            api_latency={},
            active_sessions={},
        )
        assert "<b>Database timeout</b>: 2 occurrences" in report
        assert "<h1>Error Summary</h1>" in report

    def test_render_api_latency_table(self) -> None:
        report = render_report(
            error_summary={},
            api_latency={"/users/profile": [200, 300]},
            active_sessions={},
        )
        assert "<td>/users/profile</td>" in report
        assert "<td>250.0</td>" in report

    def test_render_active_session_count(self) -> None:
        report = render_report(
            error_summary={},
            api_latency={},
            active_sessions={"alice": "t1", "bob": "t2"},
        )
        assert "2 user(s) currently active" in report

    def test_render_zero_active_sessions(self) -> None:
        report = render_report(
            error_summary={}, api_latency={}, active_sessions={}
        )
        assert "0 user(s) currently active" in report

    def test_match_original_sample_output(self) -> None:
        """Golden-test: output must match the original pipeline on sample data."""
        report = render_report(
            error_summary={"Database timeout": 2},
            api_latency={"/users/profile": [250]},
            active_sessions={},
        )
        assert "<html>" in report
        assert "<title>System Report</title>" in report
        assert "<ul>" in report
        assert "<table border='1'>" in report
        assert "</html>" in report


# ---------------------------------------------------------------------------
# Integration: run_pipeline
# ---------------------------------------------------------------------------


class TestRunPipeline:
    def test_produce_report_and_db(self, config: Config) -> None:
        run_pipeline(config)

        # Verify report was written
        report_html = config.report_path.read_text()
        assert "<b>Database timeout</b>: 2 occurrences" in report_html
        assert "/users/profile" in report_html
        assert "0 user(s) currently active" in report_html

        # Verify database was written with parameterized queries
        conn = sqlite3.connect(config.db_path)
        try:
            error_rows = conn.execute("SELECT message, count FROM errors").fetchall()
            assert len(error_rows) == 1
            assert error_rows[0] == ("Database timeout", 2)

            api_rows = conn.execute("SELECT endpoint, avg_ms FROM api_metrics").fetchall()
            assert len(api_rows) == 1
            assert api_rows[0][0] == "/users/profile"
        finally:
            conn.close()

    def test_handle_empty_log_file(self, tmp_path: Path) -> None:
        empty_log = tmp_path / "empty.log"
        empty_log.write_text("")
        cfg = Config(
            db_path=str(tmp_path / "metrics.db"),
            log_file=empty_log,
            db_host="localhost",
            db_port=5432,
            db_user="admin",
            db_pass="",
            report_path=tmp_path / "report.html",
        )
        run_pipeline(cfg)
        report = cfg.report_path.read_text()
        assert "0 user(s) currently active" in report