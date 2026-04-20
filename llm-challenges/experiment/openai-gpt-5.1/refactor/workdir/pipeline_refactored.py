"""Refactored log processing pipeline.

This module implements an Extract → Transform → Load (ETL) pipeline
for processing server logs, aggregating metrics, storing them in a
SQLite database, and generating an HTML report.

Configuration is provided via environment variables:

- PIPELINE_DB_PATH: path to SQLite database file (default: "metrics.db")
- PIPELINE_LOG_FILE: path to server log file (default: "server.log")
- PIPELINE_DB_HOST: database host for logging purposes only (default: "localhost")
- PIPELINE_DB_PORT: database port for logging purposes only (default: "5432")
- PIPELINE_DB_USER: database user for logging purposes only (default: "admin")
- PIPELINE_DB_PASS: database password for logging purposes only (default: "password123")

The produced HTML report matches the original script's report.html
structure and content (error summary, API latency table, active
session count), so downstream consumers are unaffected.
"""

from __future__ import annotations

import datetime as _dt
import os
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Tuple


# -----------------------------
# Configuration
# -----------------------------


@dataclass(frozen=True)
class PipelineConfig:
    """Runtime configuration for the log processing pipeline.

    Values are primarily sourced from environment variables, with
    sensible defaults to preserve the original behavior.
    """

    db_path: Path
    log_file: Path
    db_host: str
    db_port: int
    db_user: str
    db_pass: str

    @staticmethod
    def from_env() -> "PipelineConfig":
        """Create configuration from environment variables.

        Environment variables (with defaults):
        - PIPELINE_DB_PATH
        - PIPELINE_LOG_FILE
        - PIPELINE_DB_HOST
        - PIPELINE_DB_PORT
        - PIPELINE_DB_USER
        - PIPELINE_DB_PASS
        """

        db_path = Path(os.getenv("PIPELINE_DB_PATH", "metrics.db"))
        log_file = Path(os.getenv("PIPELINE_LOG_FILE", "server.log"))
        db_host = os.getenv("PIPELINE_DB_HOST", "localhost")
        db_port_raw = os.getenv("PIPELINE_DB_PORT", "5432")
        db_user = os.getenv("PIPELINE_DB_USER", "admin")
        db_pass = os.getenv("PIPELINE_DB_PASS", "password123")

        try:
            db_port = int(db_port_raw)
        except ValueError:
            db_port = 5432

        return PipelineConfig(
            db_path=db_path,
            log_file=log_file,
            db_host=db_host,
            db_port=db_port,
            db_user=db_user,
            db_pass=db_pass,
        )


# -----------------------------
# Data models
# -----------------------------


@dataclass
class LogEvent:
    """Base class for parsed log events."""

    timestamp: _dt.datetime
    level: str


@dataclass
class ErrorEvent(LogEvent):
    """Represents an ERROR log line."""

    message: str


@dataclass
class UserEvent(LogEvent):
    """Represents a user session-related INFO log line."""

    user_id: str
    action: str


@dataclass
class ApiCallEvent(LogEvent):
    """Represents an API latency INFO log line."""

    endpoint: str
    duration_ms: int


# -----------------------------
# Extract
# -----------------------------


# Example line formats the parser targets (matching the original script):
# 2024-01-01 12:05:00 ERROR Database timeout
# 2024-01-01 12:00:00 INFO User 42 logged in
# 2024-01-01 12:08:00 INFO API /users/profile took 250ms
# 2024-01-01 12:09:00 WARN Memory usage at 87%

_LOG_LINE_RE = re.compile(
    r"^(?P<date>\d{4}-\d{2}-\d{2})\s+"
    r"(?P<time>\d{2}:\d{2}:\d{2})\s+"
    r"(?P<level>\S+)\s+"
    r"(?P<rest>.*)$"
)

_USER_EVENT_RE = re.compile(r"^User\s+(?P<user_id>\S+)\s+(?P<action>.+)$")
_API_EVENT_RE = re.compile(
    r"^API\s+(?P<endpoint>\S+)\s+.*?took\s+(?P<duration>\d+)ms\b"
)


def parse_log_line(line: str) -> Tuple[LogEvent | None, bool]:
    """Parse a single log line into a structured event.

    Returns a tuple of (event, parsed), where:
    - event: a concrete LogEvent subclass instance or None if the
      line is not of interest.
    - parsed: True if the line matched the general log format, even
      if it did not yield an event we track; False otherwise.

    This mirrors the original behavior while using robust regex-based
    parsing instead of ad-hoc string splitting.
    """

    line = line.rstrip("\n")
    m = _LOG_LINE_RE.match(line)
    if not m:
        return None, False

    ts_str = f"{m.group('date')} {m.group('time')}"
    level = m.group("level")
    rest = m.group("rest")

    # The original script treated the timestamp as an opaque string,
    # but parsing to datetime is useful; we can still render it
    # back to string when needed.
    timestamp = _dt.datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")

    if level == "ERROR":
        # Entire rest-of-line message
        message = rest.strip()
        return ErrorEvent(timestamp=timestamp, level=level, message=message), True

    if level == "INFO":
        # User session events
        um = _USER_EVENT_RE.match(rest)
        if um:
            user_id = um.group("user_id")
            action = um.group("action").strip()
            return (
                UserEvent(
                    timestamp=timestamp,
                    level=level,
                    user_id=user_id,
                    action=action,
                ),
                True,
            )

        # API latency events
        am = _API_EVENT_RE.match(rest)
        if am:
            endpoint = am.group("endpoint")
            duration_ms = int(am.group("duration"))
            return (
                ApiCallEvent(
                    timestamp=timestamp,
                    level=level,
                    endpoint=endpoint,
                    duration_ms=duration_ms,
                ),
                True,
            )

    # WARN lines and other levels are not needed beyond existence in
    # the original script (WARN were stored but not reported); we do
    # not track them for reporting.
    return None, True


def extract_events(log_file: Path) -> Tuple[List[LogEvent], Dict[str, _dt.datetime], List[ApiCallEvent]]:
    """Extract structured events from a log file.

    Returns:
        events: list of all error and user events (for potential
            extension; used for error aggregation).
        active_sessions: mapping of user_id → login timestamp for
            currently active sessions (users logged in but not out).
        api_calls: list of API call events for latency statistics.
    """

    events: List[LogEvent] = []
    active_sessions: Dict[str, _dt.datetime] = {}
    api_calls: List[ApiCallEvent] = []

    if not log_file.exists():
        return events, active_sessions, api_calls

    with log_file.open("r", encoding="utf-8") as f:
        for raw_line in f:
            event, parsed = parse_log_line(raw_line)
            if not parsed:
                # Skip lines that do not even match the base format
                continue

            if event is None:
                # Something we don't track (e.g., WARN)
                continue

            if isinstance(event, ErrorEvent):
                events.append(event)
            elif isinstance(event, UserEvent):
                events.append(event)
                # Maintain active session set like original logic
                if "logged in" in event.action:
                    active_sessions[event.user_id] = event.timestamp
                elif "logged out" in event.action and event.user_id in active_sessions:
                    active_sessions.pop(event.user_id)
            elif isinstance(event, ApiCallEvent):
                api_calls.append(event)

    return events, active_sessions, api_calls


# -----------------------------
# Transform
# -----------------------------


def aggregate_errors(events: Iterable[LogEvent]) -> Dict[str, int]:
    """Aggregate error events into a mapping of message → count.

    Only :class:`ErrorEvent` instances contribute to the counts.
    """

    error_counts: Dict[str, int] = {}
    for event in events:
        if isinstance(event, ErrorEvent):
            msg = event.message
            error_counts[msg] = error_counts.get(msg, 0) + 1
    return error_counts


def compute_api_latency(api_calls: Iterable[ApiCallEvent]) -> Dict[str, List[int]]:
    """Group API call durations by endpoint.

    Returns a mapping of endpoint → list of durations in milliseconds.
    Average latency can be derived by the caller via ``sum / len``.
    """

    endpoint_stats: Dict[str, List[int]] = {}
    for call in api_calls:
        endpoint_stats.setdefault(call.endpoint, []).append(call.duration_ms)
    return endpoint_stats


# -----------------------------
# Load (database + report)
# -----------------------------


def init_db(connection: sqlite3.Connection) -> None:
    """Create required tables if they do not already exist."""

    cursor = connection.cursor()
    cursor.execute(
        "CREATE TABLE IF NOT EXISTS errors (dt TEXT, message TEXT, count INTEGER)"
    )
    cursor.execute(
        "CREATE TABLE IF NOT EXISTS api_metrics (dt TEXT, endpoint TEXT, avg_ms REAL)"
    )
    connection.commit()


def store_metrics(
    connection: sqlite3.Connection,
    error_counts: Mapping[str, int],
    endpoint_stats: Mapping[str, Iterable[int]],
    now: _dt.datetime | None = None,
) -> None:
    """Persist aggregated metrics into the database using parameterized queries.

    Args:
        connection: open SQLite connection.
        error_counts: mapping of error message → occurrence count.
        endpoint_stats: mapping of endpoint → iterable of durations in ms.
        now: timestamp to associate with the metrics; if omitted, the
            current time is used.
    """

    if now is None:
        now = _dt.datetime.now()

    cursor = connection.cursor()

    # Insert error aggregates
    for message, count in error_counts.items():
        cursor.execute(
            "INSERT INTO errors (dt, message, count) VALUES (?, ?, ?)",
            (now.isoformat(sep=" ", timespec="seconds"), message, count),
        )

    # Insert API latency aggregates
    for endpoint, durations in endpoint_stats.items():
        durations_list = list(durations)
        if not durations_list:
            continue
        avg_ms = sum(durations_list) / len(durations_list)
        cursor.execute(
            "INSERT INTO api_metrics (dt, endpoint, avg_ms) VALUES (?, ?, ?)",
            (now.isoformat(sep=" ", timespec="seconds"), endpoint, avg_ms),
        )

    connection.commit()


def render_report_html(
    error_counts: Mapping[str, int],
    endpoint_stats: Mapping[str, Iterable[int]],
    active_sessions: Mapping[str, _dt.datetime],
) -> str:
    """Render the HTML report matching the original script's structure.

    The content mirrors the previous implementation:
    - Error Summary list with message and occurrence count.
    - API Latency table with average duration by endpoint.
    - Active Sessions count paragraph.
    """

    # Error summary
    out = "<html>\n<head><title>System Report</title></head>\n<body>\n"
    out += "<h1>Error Summary</h1>\n<ul>\n"
    for err_msg, count in error_counts.items():
        out += f"<li><b>{err_msg}</b>: {count} occurrences</li>\n"
    out += "</ul>\n"

    # API latency
    out += "<h2>API Latency</h2>\n<table border='1'>\n"
    out += "<tr><th>Endpoint</th><th>Avg (ms)</th></tr>\n"
    for endpoint, durations in endpoint_stats.items():
        durations_list = list(durations)
        if not durations_list:
            continue
        avg = sum(durations_list) / len(durations_list)
        out += f"<tr><td>{endpoint}</td><td>{round(avg, 1)}</td></tr>\n"
    out += "</table>\n"

    # Active sessions
    out += "<h2>Active Sessions</h2>\n"
    out += f"<p>{len(active_sessions)} user(s) currently active</p>\n"
    out += "</body>\n</html>"

    return out


def write_report(report_html: str, output_path: Path) -> None:
    """Write the HTML report to disk."""

    with output_path.open("w", encoding="utf-8") as f:
        f.write(report_html)


# -----------------------------
# Orchestration
# -----------------------------


def run_pipeline(config: PipelineConfig) -> None:
    """Run the full ETL pipeline using the provided configuration."""

    print(
        f"Connecting to {config.db_host}:{config.db_port} as {config.db_user}...",
    )

    events, active_sessions, api_calls = extract_events(config.log_file)

    error_counts = aggregate_errors(events)
    endpoint_stats = compute_api_latency(api_calls)

    connection = sqlite3.connect(str(config.db_path))
    try:
        init_db(connection)
        store_metrics(connection, error_counts, endpoint_stats)
    finally:
        connection.close()

    html = render_report_html(error_counts, endpoint_stats, active_sessions)
    # Preserve original output filename
    write_report(html, Path("report.html"))

    print(f"Job finished at {_dt.datetime.now()}")


def _bootstrap_example_log(log_file: Path) -> None:
    """Create an example log file if it does not exist.

    This mirrors the behavior of the original script's __main__ block
    to keep the quick demo workflow intact.
    """

    if log_file.exists():
        return

    lines = [
        "2024-01-01 12:00:00 INFO User 42 logged in\n",
        "2024-01-01 12:05:00 ERROR Database timeout\n",
        "2024-01-01 12:05:05 ERROR Database timeout\n",
        "2024-01-01 12:08:00 INFO API /users/profile took 250ms\n",
        "2024-01-01 12:09:00 WARN Memory usage at 87%\n",
        "2024-01-01 12:10:00 INFO User 42 logged out\n",
    ]

    with log_file.open("w", encoding="utf-8") as f:
        f.writelines(lines)


if __name__ == "__main__":
    cfg = PipelineConfig.from_env()
    _bootstrap_example_log(cfg.log_file)
    run_pipeline(cfg)
