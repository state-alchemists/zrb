"""
Log processing pipeline: parse server logs, extract metrics, persist to SQLite,
and generate an HTML report.

Usage:
    export PIPELINE_LOG_FILE=server.log   # default: server.log
    export PIPELINE_DB_PATH=metrics.db    # default: metrics.db
    python pipeline_refactored.py

Output: report.html
"""

from __future__ import annotations

import datetime
import os
import re
import sqlite3
from collections import Counter, defaultdict
from typing import NamedTuple


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

class Config(NamedTuple):
    """Environment-driven configuration with sensible defaults."""

    log_file: str = os.environ.get("PIPELINE_LOG_FILE", "server.log")
    db_path: str = os.environ.get("PIPELINE_DB_PATH", "metrics.db")


# ---------------------------------------------------------------------------
# Domain models
# ---------------------------------------------------------------------------

class LogEntry(NamedTuple):
    """A single parsed log line."""

    timestamp: str
    level: str
    message: str


class ApiCall(NamedTuple):
    """An API latency measurement."""

    timestamp: str
    endpoint: str
    duration_ms: int


class ErrorCount(NamedTuple):
    """Aggregated error message with occurrence count."""

    message: str
    count: int


class ParsedLogs(NamedTuple):
    """Container for all data extracted during the parse phase."""

    errors: list[LogEntry]
    api_calls: list[ApiCall]
    active_sessions: dict[str, str]


# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

LOG_LINE_RE = re.compile(
    r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s+"
    r"(INFO|ERROR|WARN)\s+"
    r"(.+)$"
)

USER_ACTION_RE = re.compile(r"^User\s+(\S+)\s+(.+)$")

API_LATENCY_RE = re.compile(r"^API\s+(\/\S+)\s+took\s+(\d+)ms$")


# ---------------------------------------------------------------------------
# Phase 1: Extract
# ---------------------------------------------------------------------------

def read_log_lines(config: Config) -> list[str]:
    """Read all non-empty lines from the configured log file.

    Returns an empty list if the file does not exist.
    """
    if not os.path.exists(config.log_file):
        print(f"Log file not found: {config.log_file} \u2014 nothing to process")
        return []
    with open(config.log_file, "r") as f:
        return [line.rstrip("\n") for line in f if line.strip()]


# ---------------------------------------------------------------------------
# Phase 2: Transform
# ---------------------------------------------------------------------------

def parse_log_lines(lines: list[str]) -> ParsedLogs:
    """Parse raw log lines into structured error, API, and session data.

    Session tracking is stateful: *logged in* starts a session and *logged out*
    removes it. Only the **current active sessions** are returned (users who have
    logged in but not yet logged out within the parsed window).
    """
    errors: list[LogEntry] = []
    api_calls: list[ApiCall] = []
    sessions: dict[str, str] = {}

    for line in lines:
        match = LOG_LINE_RE.match(line)
        if not match:
            continue
        timestamp, level, message = match.groups()

        if level == "ERROR":
            errors.append(LogEntry(timestamp, level, message))

        elif level == "WARN":
            errors.append(LogEntry(timestamp, level, message))

        elif level == "INFO":
            _try_parse_user_action(timestamp, message, sessions)
            api = _try_parse_api_call(timestamp, message)
            if api is not None:
                api_calls.append(api)

    return ParsedLogs(errors=errors, api_calls=api_calls, active_sessions=sessions)


def _try_parse_user_action(
    timestamp: str, message: str, sessions: dict[str, str]
) -> None:
    """If *message* describes a user login/logout, update *sessions* in place."""
    m = USER_ACTION_RE.match(message)
    if not m:
        return
    user_id, action = m.groups()
    if "logged in" in action:
        sessions[user_id] = timestamp
    elif "logged out" in action and user_id in sessions:
        del sessions[user_id]


def _try_parse_api_call(timestamp: str, message: str) -> ApiCall | None:
    """Return an ``ApiCall`` if *message* describes API latency, else ``None``."""
    m = API_LATENCY_RE.match(message)
    if not m:
        return None
    return ApiCall(timestamp=timestamp, endpoint=m.group(1), duration_ms=int(m.group(2)))


def aggregate_errors(errors: list[LogEntry]) -> list[ErrorCount]:
    """Group error entries by message text and count occurrences."""
    counts: Counter[str] = Counter()
    for entry in errors:
        if entry.level == "ERROR":
            counts[entry.message] += 1
    return [ErrorCount(msg, cnt) for msg, cnt in counts.most_common()]


def aggregate_api_latency(api_calls: list[ApiCall]) -> dict[str, float]:
    """Compute average latency per API endpoint."""
    totals: dict[str, list[int]] = defaultdict(list)
    for call in api_calls:
        totals[call.endpoint].append(call.duration_ms)
    return {ep: sum(times) / len(times) for ep, times in totals.items()}


# ---------------------------------------------------------------------------
# Phase 3: Load \u2014 database
# ---------------------------------------------------------------------------

def _init_db(db_path: str) -> sqlite3.Connection:
    """Create / open the SQLite database and ensure tables exist."""
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS errors "
        "(dt TEXT, message TEXT, count INTEGER)"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS api_metrics "
        "(dt TEXT, endpoint TEXT, avg_ms REAL)"
    )
    return conn


def store_error_counts(
    conn: sqlite3.Connection, error_counts: list[ErrorCount]
) -> None:
    """Insert aggregated error counts with parameterized queries."""
    now = datetime.datetime.now().isoformat()
    conn.executemany(
        "INSERT INTO errors (dt, message, count) VALUES (?, ?, ?)",
        [(now, ec.message, ec.count) for ec in error_counts],
    )


def store_api_metrics(
    conn: sqlite3.Connection, api_latency: dict[str, float]
) -> None:
    """Insert averaged API latency data with parameterized queries."""
    now = datetime.datetime.now().isoformat()
    conn.executemany(
        "INSERT INTO api_metrics (dt, endpoint, avg_ms) VALUES (?, ?, ?)",
        [(now, ep, avg) for ep, avg in api_latency.items()],
    )


# ---------------------------------------------------------------------------
# Phase 3: Load \u2014 HTML report
# ---------------------------------------------------------------------------

def _html_escape(text: str) -> str:
    """Minimal HTML escaping for safe string interpolation."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def generate_report(
    error_counts: list[ErrorCount],
    api_latency: dict[str, float],
    active_session_count: int,
) -> str:
    """Build the full ``report.html`` string from aggregated data."""
    parts: list[str] = [
        "<!DOCTYPE html>\n",
        '<html>\n<head><title>System Report</title></head>\n<body>\n',
        "<h1>Error Summary</h1>\n<ul>\n",
    ]

    for ec in error_counts:
        parts.append(
            f"<li><b>{_html_escape(ec.message)}</b>: "
            f"{ec.count} occurrences</li>\n"
        )
    parts.append("</ul>\n")

    parts.append("<h2>API Latency</h2>\n<table border='1'>\n")
    parts.append("<tr><th>Endpoint</th><th>Avg (ms)</th></tr>\n")
    for ep, avg in sorted(api_latency.items()):
        parts.append(
            f"<tr><td>{_html_escape(ep)}</td>"
            f"<td>{avg:.1f}</td></tr>\n"
        )
    parts.append("</table>\n")

    parts.append("<h2>Active Sessions</h2>\n")
    parts.append(f"<p>{active_session_count} user(s) currently active</p>\n")
    parts.append("</body>\n</html>\n")

    return "".join(parts)


def write_report(report_html: str) -> None:
    """Write the HTML report to ``report.html``."""
    with open("report.html", "w") as f:
        f.write(report_html)


# ---------------------------------------------------------------------------
# Pipeline orchestration
# ---------------------------------------------------------------------------

def run_pipeline(config: Config) -> None:
    """Execute the full Extract \u2192 Transform \u2192 Load pipeline.

    Stages:
        1. **Extract** \u2014 read raw lines from the log file.
        2. **Transform** \u2014 parse lines into structured records and aggregate.
        3. **Load** \u2014 persist aggregates to SQLite and write ``report.html``.
    """
    # Extract
    lines = read_log_lines(config)
    if not lines:
        print("No log data to process.")
        return

    # Transform
    parsed = parse_log_lines(lines)
    error_counts = aggregate_errors(parsed.errors)
    api_latency = aggregate_api_latency(parsed.api_calls)

    # Load \u2014 database
    conn = _init_db(config.db_path)
    try:
        store_error_counts(conn, error_counts)
        store_api_metrics(conn, api_latency)
        conn.commit()
    finally:
        conn.close()

    # Load \u2014 report
    report_html = generate_report(
        error_counts=error_counts,
        api_latency=api_latency,
        active_session_count=len(parsed.active_sessions),
    )
    write_report(report_html)

    print(f"Pipeline finished at {datetime.datetime.now().isoformat()}")
    print(f"  Errors recorded: {len(error_counts)}")
    print(f"  API endpoints tracked: {len(api_latency)}")
    print(f"  Active sessions: {len(parsed.active_sessions)}")
    print(f"  Report written to: report.html")


# ---------------------------------------------------------------------------
# Entry point \u2014 bootstrap with sample data when no log file exists
# ---------------------------------------------------------------------------

def _ensure_sample_log(config: Config) -> None:
    """Write a sample log file if the configured log file does not exist."""
    if os.path.exists(config.log_file):
        return
    sample = (
        "2024-01-01 12:00:00 INFO User 42 logged in\n"
        "2024-01-01 12:05:00 ERROR Database timeout\n"
        "2024-01-01 12:05:05 ERROR Database timeout\n"
        "2024-01-01 12:08:00 INFO API /users/profile took 250ms\n"
        "2024-01-01 12:09:00 WARN Memory usage at 87%\n"
        "2024-01-01 12:10:00 INFO User 42 logged out\n"
    )
    with open(config.log_file, "w") as f:
        f.write(sample)
    print(f"Sample log written to {config.log_file}")


def main() -> None:
    """Entry point: ensure sample data, then run the pipeline."""
    config = Config()
    _ensure_sample_log(config)
    run_pipeline(config)


if __name__ == "__main__":
    main()
