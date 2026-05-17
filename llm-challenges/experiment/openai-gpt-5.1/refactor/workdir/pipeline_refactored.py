"""Refactored log processing pipeline.

This module parses server logs, aggregates metrics, stores them in a SQLite
database, and generates an HTML report. It preserves the original
functionality (error summary, API latency table, active session count) while
improving security and maintainability.

Configuration is provided via environment variables:

- DB_PATH: Path to SQLite database file (required)
- LOG_FILE: Path to server log file (required)
- DB_HOST: Database host (for logging only, optional)
- DB_PORT: Database port (for logging only, optional)
- DB_USER: Database user (for logging only, optional)
- DB_PASS: Database password (for logging only, optional)

The DB_* variables besides DB_PATH are not used for connections because this
pipeline uses SQLite, but they are kept for parity with the original script's
logging output.
"""

from __future__ import annotations

import datetime as dt
import os
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Tuple


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class ErrorEvent:
    """Represents an error log event."""

    timestamp: dt.datetime
    message: str


@dataclass
class ApiCall:
    """Represents a single API call with latency in milliseconds."""

    timestamp: dt.datetime
    endpoint: str
    duration_ms: int


# ---------------------------------------------------------------------------
# Configuration helpers
# ---------------------------------------------------------------------------


def get_env_config() -> Tuple[Path, Path, str, int, str, str]:
    """Read configuration from environment variables.

    Returns a tuple of:
    (db_path, log_file, db_host, db_port, db_user, db_pass).

    Raises:
        RuntimeError: If required variables (DB_PATH, LOG_FILE) are missing.
    """

    db_path_str = os.getenv("DB_PATH")
    log_file_str = os.getenv("LOG_FILE")

    if not db_path_str:
        raise RuntimeError("DB_PATH environment variable is required")
    if not log_file_str:
        raise RuntimeError("LOG_FILE environment variable is required")

    db_host = os.getenv("DB_HOST", "localhost")
    db_port_str = os.getenv("DB_PORT", "5432")
    db_user = os.getenv("DB_USER", "admin")
    db_pass = os.getenv("DB_PASS", "password123")

    try:
        db_port = int(db_port_str)
    except ValueError as exc:
        raise RuntimeError(f"Invalid DB_PORT value: {db_port_str!r}") from exc

    return (Path(db_path_str), Path(log_file_str), db_host, db_port, db_user, db_pass)


# ---------------------------------------------------------------------------
# Extract
# ---------------------------------------------------------------------------


_LOG_LINE_RE = re.compile(
    r"^(?P<date>\d{4}-\d{2}-\d{2})\s+"  # date
    r"(?P<time>\d{2}:\d{2}:\d{2})\s+"   # time
    r"(?P<level>INFO|ERROR|WARN)\s+"      # log level
    r"(?P<body>.*)$"                       # rest of line
)

_USER_EVENT_RE = re.compile(
    r"User\s+(?P<user_id>\S+)\s+(?P<action>.*)$"
)

_API_CALL_RE = re.compile(
    r"API\s+(?P<endpoint>\S+)\s+took\s+(?P<duration>\d+)ms"
)


def parse_log_line(line: str) -> Tuple[dt.datetime, str, str]:
    """Parse a raw log line into timestamp, level, and body.

    The function is intentionally strict about the leading date/time/level
    format to avoid fragile string-splitting logic.

    Returns:
        (timestamp, level, body)

    Raises:
        ValueError: If the line does not match the expected format.
    """

    match = _LOG_LINE_RE.match(line.strip())
    if not match:
        raise ValueError(f"Unrecognized log line format: {line!r}")

    ts_str = f"{match.group('date')} {match.group('time')}"
    timestamp = dt.datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
    level = match.group("level")
    body = match.group("body")
    return timestamp, level, body


def extract_events(log_path: Path) -> Tuple[List[ErrorEvent], List[ApiCall], Dict[str, dt.datetime]]:
    """Extract error events, API calls, and active sessions from the log file.

    Args:
        log_path: Path to the log file.

    Returns:
        A tuple of (errors, api_calls, active_sessions), where:
        - errors is a list of ErrorEvent instances
        - api_calls is a list of ApiCall instances
        - active_sessions maps user_id to login timestamp for currently-active users
    """

    errors: List[ErrorEvent] = []
    api_calls: List[ApiCall] = []
    sessions: Dict[str, dt.datetime] = {}

    if not log_path.exists():
        return errors, api_calls, sessions

    with log_path.open("r", encoding="utf-8") as fh:
        for raw_line in fh:
            raw_line = raw_line.rstrip("\n")
            if not raw_line.strip():
                continue

            try:
                timestamp, level, body = parse_log_line(raw_line)
            except ValueError:
                # Skip lines that don't conform to expected format
                continue

            if level == "ERROR":
                # Entire body is the error message
                errors.append(ErrorEvent(timestamp=timestamp, message=body.strip()))

            elif level == "WARN":
                # WARN messages are not currently persisted but could be handled here
                continue

            elif level == "INFO":
                # User session events
                user_match = _USER_EVENT_RE.search(body)
                if user_match:
                    user_id = user_match.group("user_id")
                    action = user_match.group("action").strip()

                    if "logged in" in action:
                        sessions[user_id] = timestamp
                    elif "logged out" in action and user_id in sessions:
                        sessions.pop(user_id, None)

                    continue

                # API latency events
                api_match = _API_CALL_RE.search(body)
                if api_match:
                    endpoint = api_match.group("endpoint")
                    duration_ms = int(api_match.group("duration"))
                    api_calls.append(
                        ApiCall(timestamp=timestamp, endpoint=endpoint, duration_ms=duration_ms)
                    )

    return errors, api_calls, sessions


# ---------------------------------------------------------------------------
# Transform
# ---------------------------------------------------------------------------


def aggregate_errors(errors: Iterable[ErrorEvent]) -> Dict[str, int]:
    """Aggregate error events into a count per error message."""

    counts: Dict[str, int] = {}
    for event in errors:
        counts[event.message] = counts.get(event.message, 0) + 1
    return counts


def aggregate_api_latency(api_calls: Iterable[ApiCall]) -> Dict[str, List[int]]:
    """Group API call durations by endpoint."""

    stats: Dict[str, List[int]] = {}
    for call in api_calls:
        stats.setdefault(call.endpoint, []).append(call.duration_ms)
    return stats


# ---------------------------------------------------------------------------
# Load (database + report generation)
# ---------------------------------------------------------------------------


def init_db(conn: sqlite3.Connection) -> None:
    """Create required tables if they do not already exist."""

    cur = conn.cursor()
    cur.execute(
        "CREATE TABLE IF NOT EXISTS errors (dt TEXT, message TEXT, count INTEGER)"
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS api_metrics (dt TEXT, endpoint TEXT, avg_ms REAL)"
    )
    conn.commit()


def load_into_db(
    conn: sqlite3.Connection,
    error_counts: Mapping[str, int],
    endpoint_stats: Mapping[str, Iterable[int]],
) -> None:
    """Persist aggregated metrics into the SQLite database using parameterized queries."""

    cur = conn.cursor()
    now_str = dt.datetime.now().isoformat(timespec="seconds")

    for message, count in error_counts.items():
        cur.execute(
            "INSERT INTO errors (dt, message, count) VALUES (?, ?, ?)",
            (now_str, message, count),
        )

    for endpoint, durations in endpoint_stats.items():
        durations_list = list(durations)
        if not durations_list:
            continue
        avg_ms = sum(durations_list) / len(durations_list)
        cur.execute(
            "INSERT INTO api_metrics (dt, endpoint, avg_ms) VALUES (?, ?, ?)",
            (now_str, endpoint, avg_ms),
        )

    conn.commit()


def render_report(
    error_counts: Mapping[str, int],
    endpoint_stats: Mapping[str, Iterable[int]],
    active_sessions: Mapping[str, dt.datetime],
) -> str:
    """Render the HTML report string.

    The structure and information mirror the original `report.html` output:
    - Error summary as a list of messages with occurrence counts
    - API latency table with average duration per endpoint
    - Count of active user sessions
    """

    html_parts: List[str] = []
    html_parts.append("<html>")
    html_parts.append("<head><title>System Report</title></head>")
    html_parts.append("<body>")

    # Error summary
    html_parts.append("<h1>Error Summary</h1>")
    html_parts.append("<ul>")
    for msg, count in error_counts.items():
        html_parts.append(
            f"<li><b>{msg}</b>: {count} occurrences</li>"
        )
    html_parts.append("</ul>")

    # API latency
    html_parts.append("<h2>API Latency</h2>")
    html_parts.append("<table border='1'>")
    html_parts.append("<tr><th>Endpoint</th><th>Avg (ms)</th></tr>")
    for endpoint, durations in endpoint_stats.items():
        durations_list = list(durations)
        if not durations_list:
            continue
        avg = sum(durations_list) / len(durations_list)
        html_parts.append(
            f"<tr><td>{endpoint}</td><td>{round(avg, 1)}</td></tr>"
        )
    html_parts.append("</table>")

    # Active sessions
    html_parts.append("<h2>Active Sessions</h2>")
    html_parts.append(
        f"<p>{len(active_sessions)} user(s) currently active</p>"
    )

    html_parts.append("</body>")
    html_parts.append("</html>")

    return "\n".join(html_parts)


def run_pipeline() -> None:
    """Execute the full Extract → Transform → Load pipeline and write report.html."""

    db_path, log_file, db_host, db_port, db_user, _db_pass = get_env_config()

    print(f"Connecting to {db_host}:{db_port} as {db_user}...")

    # Extract
    errors, api_calls, sessions = extract_events(log_file)

    # Transform
    error_counts = aggregate_errors(errors)
    endpoint_stats = aggregate_api_latency(api_calls)

    # Load into DB
    conn = sqlite3.connect(str(db_path))
    try:
        init_db(conn)
        load_into_db(conn, error_counts, endpoint_stats)
    finally:
        conn.close()

    # Generate HTML report
    report_html = render_report(error_counts, endpoint_stats, sessions)
    with open("report.html", "w", encoding="utf-8") as fh:
        fh.write(report_html)

    print(f"Job finished at {dt.datetime.now()}")


if __name__ == "__main__":
    # Preserve the original behavior of seeding a demo log file when missing.
    # The file path is now determined by LOG_FILE env var.
    _, log_file, *_rest = get_env_config()

    if not log_file.exists():
        log_file.parent.mkdir(parents=True, exist_ok=True)
        with log_file.open("w", encoding="utf-8") as fh:
            fh.write("2024-01-01 12:00:00 INFO User 42 logged in\n")
            fh.write("2024-01-01 12:05:00 ERROR Database timeout\n")
            fh.write("2024-01-01 12:05:05 ERROR Database timeout\n")
            fh.write("2024-01-01 12:08:00 INFO API /users/profile took 250ms\n")
            fh.write("2024-01-01 12:09:00 WARN Memory usage at 87%\n")
            fh.write("2024-01-01 12:10:00 INFO User 42 logged out\n")

    run_pipeline()
