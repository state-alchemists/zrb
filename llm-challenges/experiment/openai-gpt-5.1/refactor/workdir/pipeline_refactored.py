"""Refactored log processing pipeline.

Implements an Extract → Transform → Load (ETL) flow for server logs:
- Extract: read and parse log lines using regex
- Transform: aggregate error counts, API latency, and active sessions
- Load: persist metrics into SQLite using parameterized queries and render an HTML report

Configuration is provided via environment variables:
- DB_PATH: path to SQLite database file (default: "metrics.db")
- LOG_FILE: path to log file (default: "server.log")
- DB_HOST, DB_PORT, DB_USER, DB_PASS: connection info (informational only for SQLite)

The generated HTML report contains the same information as the original pipeline:
- Error summary
- API latency table
- Active session count
"""

from __future__ import annotations

import datetime as _dt
import os
import re
import sqlite3
from dataclasses import dataclass
from typing import Dict, Iterable, List, Mapping, Tuple


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class LogRecord:
    """Represents a generic parsed log record.

    Attributes:
        timestamp: Datetime string as found in the log (e.g. "2024-01-01 12:00:00").
        level: Log level string (e.g. "INFO", "ERROR", "WARN").
        message: Remainder of the log line after the level.
        raw_line: Original log line, for debugging or future extensions.
    """

    timestamp: str
    level: str
    message: str
    raw_line: str


@dataclass
class ErrorEvent:
    """An extracted error event from the logs."""

    timestamp: str
    message: str


@dataclass
class UserEvent:
    """A user login/logout event."""

    timestamp: str
    user_id: str
    action: str


@dataclass
class ApiCall:
    """An API call latency measurement."""

    timestamp: str
    endpoint: str
    duration_ms: int


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


def get_config() -> Mapping[str, str]:
    """Return configuration derived from environment variables.

    Environment variables (with defaults matching the original script):
        DB_PATH: SQLite database path (default: "metrics.db").
        LOG_FILE: Log file path (default: "server.log").
        DB_HOST: Database host (default: "localhost").
        DB_PORT: Database port (default: "5432").
        DB_USER: Database user (default: "admin").
        DB_PASS: Database password (default: "password123").

    Returns:
        Mapping of configuration keys to their resolved string values.
    """

    return {
        "DB_PATH": os.getenv("DB_PATH", "metrics.db"),
        "LOG_FILE": os.getenv("LOG_FILE", "server.log"),
        "DB_HOST": os.getenv("DB_HOST", "localhost"),
        "DB_PORT": os.getenv("DB_PORT", "5432"),
        "DB_USER": os.getenv("DB_USER", "admin"),
        "DB_PASS": os.getenv("DB_PASS", "password123"),
    }


# ---------------------------------------------------------------------------
# Extract
# ---------------------------------------------------------------------------


# Example log format used in the original script:
# 2024-01-01 12:00:00 INFO User 42 logged in
# 2024-01-01 12:08:00 INFO API /users/profile took 250ms
# 2024-01-01 12:09:00 WARN Memory usage at 87%
# 2024-01-01 12:05:00 ERROR Database timeout

_LOG_LINE_RE = re.compile(r"^(?P<date>\d{4}-\d{2}-\d{2})\\s+(?P<time>\d{2}:\d{2}:\d{2})\\s+(?P<level>[A-Z]+)\\s+(?P<message>.*)$")
_USER_EVENT_RE = re.compile(r"User\\s+(?P<user_id>\\S+)\\s+(?P<action>.+)$")
_API_CALL_RE = re.compile(r"API\\s+(?P<endpoint>\\S+)\\s+.*?took\\s+(?P<duration>\\d+)ms")


def read_log_lines(path: str) -> Iterable[str]:
    """Yield raw log lines from the given file path.

    If the file does not exist, yields nothing.
    """

    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return f.readlines()


def parse_log_line(line: str) -> LogRecord | None:
    """Parse a single log line into a :class:`LogRecord` using regex.

    Returns ``None`` if the line does not match the expected format.
    """

    match = _LOG_LINE_RE.match(line.strip())
    if not match:
        return None
    timestamp = f"{match.group('date')} {match.group('time')}"
    level = match.group("level")
    message = match.group("message")
    return LogRecord(timestamp=timestamp, level=level, message=message, raw_line=line.rstrip("\n"))


def extract_events(records: Iterable[LogRecord]) -> Tuple[List[ErrorEvent], List[UserEvent], List[ApiCall]]:
    """Extract domain-specific events from a sequence of :class:`LogRecord` objects.

    This preserves the behavior of the original script:
    - ERROR lines contribute to error events.
    - INFO lines mentioning "User" generate user events and update session state.
    - INFO lines mentioning "API" with a latency produce API call events.

    Session state itself is later derived from the resulting user events.
    """

    errors: List[ErrorEvent] = []
    users: List[UserEvent] = []
    api_calls: List[ApiCall] = []

    for record in records:
        lvl = record.level
        msg = record.message

        if lvl == "ERROR":
            errors.append(ErrorEvent(timestamp=record.timestamp, message=msg))
        elif lvl == "INFO" and "User" in msg:
            user_match = _USER_EVENT_RE.search(msg)
            if not user_match:
                continue
            user_id = user_match.group("user_id")
            action = user_match.group("action")
            users.append(UserEvent(timestamp=record.timestamp, user_id=user_id, action=action))
        elif lvl == "INFO" and "API" in msg:
            api_match = _API_CALL_RE.search(msg)
            if not api_match:
                continue
            endpoint = api_match.group("endpoint")
            duration_ms = int(api_match.group("duration"))
            api_calls.append(ApiCall(timestamp=record.timestamp, endpoint=endpoint, duration_ms=duration_ms))

    return errors, users, api_calls


# ---------------------------------------------------------------------------
# Transform
# ---------------------------------------------------------------------------


def aggregate_errors(errors: Iterable[ErrorEvent]) -> Dict[str, int]:
    """Aggregate errors by message, returning a mapping of message → count."""

    counts: Dict[str, int] = {}
    for e in errors:
        counts[e.message] = counts.get(e.message, 0) + 1
    return counts


def compute_api_stats(api_calls: Iterable[ApiCall]) -> Dict[str, List[int]]:
    """Group API call durations by endpoint.

    Returns:
        Mapping of endpoint → list of duration measurements in milliseconds.
    """

    stats: Dict[str, List[int]] = {}
    for call in api_calls:
        stats.setdefault(call.endpoint, []).append(call.duration_ms)
    return stats


def count_active_sessions(events: Iterable[UserEvent]) -> int:
    """Compute the number of currently active user sessions.

    Follows the original logic:
    - "logged in" adds a session for the user.
    - "logged out" removes the session for the user if present.
    """

    sessions: Dict[str, str] = {}
    for e in events:
        if "logged in" in e.action:
            sessions[e.user_id] = e.timestamp
        elif "logged out" in e.action and e.user_id in sessions:
            sessions.pop(e.user_id)
    return len(sessions)


# ---------------------------------------------------------------------------
# Load (DB + HTML report)
# ---------------------------------------------------------------------------


def init_db(conn: sqlite3.Connection) -> None:
    """Create the required tables if they do not exist."""

    cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS errors (dt TEXT, message TEXT, count INTEGER)")
    cur.execute("CREATE TABLE IF NOT EXISTS api_metrics (dt TEXT, endpoint TEXT, avg_ms REAL)")
    conn.commit()


def store_metrics(
    conn: sqlite3.Connection,
    error_counts: Mapping[str, int],
    api_stats: Mapping[str, List[int]],
) -> None:
    """Persist aggregated metrics into the database using parameterized queries.

    Args:
        conn: Open SQLite connection.
        error_counts: Mapping of error message → occurrence count.
        api_stats: Mapping of endpoint → list of latency measurements.
    """

    cur = conn.cursor()
    now_str = _dt.datetime.now().isoformat(sep=" ", timespec="seconds")

    for msg, count in error_counts.items():
        cur.execute(
            "INSERT INTO errors (dt, message, count) VALUES (?, ?, ?)",
            (now_str, msg, count),
        )

    for endpoint, durations in api_stats.items():
        if not durations:
            continue
        avg_ms = sum(durations) / len(durations)
        cur.execute(
            "INSERT INTO api_metrics (dt, endpoint, avg_ms) VALUES (?, ?, ?)",
            (now_str, endpoint, avg_ms),
        )

    conn.commit()


def render_report_html(
    error_counts: Mapping[str, int],
    api_stats: Mapping[str, List[int]],
    active_sessions: int,
) -> str:
    """Render the HTML report with the same information as the original script.

    Args:
        error_counts: Mapping of error message → occurrence count.
        api_stats: Mapping of endpoint → list of duration measurements.
        active_sessions: Number of currently active user sessions.

    Returns:
        HTML string.
    """

    out_lines: List[str] = []
    out_lines.append("<html>")
    out_lines.append("<head><title>System Report</title></head>")
    out_lines.append("<body>")

    # Error summary
    out_lines.append("<h1>Error Summary</h1>")
    out_lines.append("<ul>")
    for err_msg, count in error_counts.items():
        out_lines.append(f"<li><b>{err_msg}</b>: {count} occurrences</li>")
    out_lines.append("</ul>")

    # API latency
    out_lines.append("<h2>API Latency</h2>")
    out_lines.append("<table border='1'>")
    out_lines.append("<tr><th>Endpoint</th><th>Avg (ms)</th></tr>")
    for endpoint, durations in api_stats.items():
        if not durations:
            continue
        avg = sum(durations) / len(durations)
        out_lines.append(
            f"<tr><td>{endpoint}</td><td>{round(avg, 1)}</td></tr>"
        )
    out_lines.append("</table>")

    # Active sessions
    out_lines.append("<h2>Active Sessions</h2>")
    out_lines.append(f"<p>{active_sessions} user(s) currently active</p>")

    out_lines.append("</body>")
    out_lines.append("</html>")

    return "\n".join(out_lines) + "\n"


def write_report(path: str, html: str) -> None:
    """Write the HTML report to disk."""

    with open(path, "w", encoding="utf-8") as f:
        f.write(html)


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def run_pipeline() -> None:
    """Execute the full ETL pipeline from log file to DB + HTML report."""

    cfg = get_config()

    # Extract
    raw_lines = read_log_lines(cfg["LOG_FILE"])
    records = [r for line in raw_lines if (r := parse_log_line(line)) is not None]
    errors, user_events, api_calls = extract_events(records)

    # Transform
    error_counts = aggregate_errors(errors)
    api_stats = compute_api_stats(api_calls)
    active_sessions = count_active_sessions(user_events)

    # Load: database
    print(
        f"Connecting to {cfg['DB_HOST']}:{cfg['DB_PORT']} as {cfg['DB_USER']}..."
    )
    conn = sqlite3.connect(cfg["DB_PATH"])
    try:
        init_db(conn)
        store_metrics(conn, error_counts, api_stats)
    finally:
        conn.close()

    # Load: HTML report
    html = render_report_html(error_counts, api_stats, active_sessions)
    write_report("report.html", html)

    print(f"Job finished at {_dt.datetime.now()}")


if __name__ == "__main__":
    cfg = get_config()
    log_file = cfg["LOG_FILE"]
    if not os.path.exists(log_file):
        with open(log_file, "w", encoding="utf-8") as f:
            f.write("2024-01-01 12:00:00 INFO User 42 logged in\n")
            f.write("2024-01-01 12:05:00 ERROR Database timeout\n")
            f.write("2024-01-01 12:05:05 ERROR Database timeout\n")
            f.write("2024-01-01 12:08:00 INFO API /users/profile took 250ms\n")
            f.write("2024-01-01 12:09:00 WARN Memory usage at 87%\n")
            f.write("2024-01-01 12:10:00 INFO User 42 logged out\n")
    run_pipeline()
