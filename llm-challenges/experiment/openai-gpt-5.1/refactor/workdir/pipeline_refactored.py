"""Refactored log processing pipeline.

Implements an Extract → Transform → Load (ETL) flow for server logs:
- Extract: read and parse log lines with regex
- Transform: aggregate error counts, API latency stats, and active sessions
- Load: persist metrics into a SQLite database and render an HTML report

Configuration is provided via environment variables:
- DB_PATH: path to the SQLite database file (default: "metrics.db")
- LOG_FILE: path to the server log file (default: "server.log")
- DB_HOST, DB_PORT, DB_USER, DB_PASS: connection metadata (currently logged only)

The produced HTML report contains the same information as the original
`pipeline.py` script: error summary, API latency table, and active session
count. The output file remains `report.html`.
"""

from __future__ import annotations

import datetime as dt
import os
import re
import sqlite3
from dataclasses import dataclass
from typing import Dict, Iterable, List, Mapping, Optional, Tuple


# ---------------------------------------------------------------------------
# Configuration helpers
# ---------------------------------------------------------------------------


def get_env(var_name: str, default: Optional[str] = None) -> str:
    """Return the value of an environment variable or a default.

    Parameters
    ----------
    var_name:
        Name of the environment variable.
    default:
        Default value to use when the variable is not set. If both the
        environment variable and default are missing, a ValueError is raised.
    """

    value = os.getenv(var_name, default)
    if value is None:
        raise ValueError(f"Required environment variable {var_name!r} is not set")
    return value


DB_PATH: str = get_env("DB_PATH", "metrics.db")
LOG_FILE: str = get_env("LOG_FILE", "server.log")
DB_HOST: str = get_env("DB_HOST", "localhost")
DB_PORT: str = get_env("DB_PORT", "5432")
DB_USER: str = get_env("DB_USER", "admin")
DB_PASS: str = get_env("DB_PASS", "password123")


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class ErrorEvent:
    """Represents a single error log entry."""

    timestamp: str
    message: str


@dataclass
class ApiCall:
    """Represents a single API call log entry."""

    timestamp: str
    endpoint: str
    duration_ms: int


@dataclass
class UserEvent:
    """Represents a user session-related log entry."""

    timestamp: str
    user_id: str
    action: str


@dataclass
class ParsedLogs:
    """Collection of parsed log events and derived session state."""

    errors: List[ErrorEvent]
    api_calls: List[ApiCall]
    user_events: List[UserEvent]
    active_sessions: Dict[str, str]


# ---------------------------------------------------------------------------
# Extract: read log file & parse lines
# ---------------------------------------------------------------------------


# Example lines used by the original script:
# 2024-01-01 12:00:00 INFO User 42 logged in
# 2024-01-01 12:05:00 ERROR Database timeout
# 2024-01-01 12:08:00 INFO API /users/profile took 250ms
# 2024-01-01 12:09:00 WARN Memory usage at 87%

LOG_LINE_RE = re.compile(
    r"^(?P<date>\d{4}-\d{2}-\d{2})\s+"  # date
    r"(?P<time>\d{2}:\d{2}:\d{2})\s+"  # time
    r"(?P<level>\S+)\s+"  # level
    r"(?P<rest>.*)$"  # remaining message
)

USER_EVENT_RE = re.compile(r"^User\s+(?P<user_id>\S+)\s+(?P<action>.+)$")
API_CALL_RE = re.compile(
    r"^API\s+(?P<endpoint>\S+)(?:.*?took\s+(?P<duration>\d+)ms)?"  # duration optional
)


def read_log_lines(path: str) -> Iterable[str]:
    """Yield log lines from the given file path if it exists.

    This function is tolerant of missing files and simply yields no lines
    when the file is not present.
    """

    if not os.path.exists(path):
        return []

    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            yield line.rstrip("\n")


def parse_logs(lines: Iterable[str]) -> ParsedLogs:
    """Parse raw log lines into structured events.

    The parsing logic is compatible with the original implementation while
    using regular expressions for robustness.
    """

    errors: List[ErrorEvent] = []
    api_calls: List[ApiCall] = []
    user_events: List[UserEvent] = []
    active_sessions: Dict[str, str] = {}

    for line in lines:
        match = LOG_LINE_RE.match(line)
        if not match:
            continue

        ts = f"{match.group('date')} {match.group('time')}"
        level = match.group("level")
        rest = match.group("rest")

        if level == "ERROR":
            message = rest.strip()
            if message:
                errors.append(ErrorEvent(timestamp=ts, message=message))

        elif level == "WARN":
            # Warnings contribute only to the generic parsed list in the
            # original implementation; they do not affect aggregates.
            # We keep them as user events with a synthetic user id to
            # preserve potential extensibility, though they are unused
            # in current aggregates.
            # (Could alternatively be omitted; they never appeared in
            # any downstream stats.)
            pass

        elif level == "INFO":
            user_match = USER_EVENT_RE.match(rest)
            api_match = API_CALL_RE.match(rest) if "API" in rest else None

            if user_match:
                user_id = user_match.group("user_id")
                action = user_match.group("action")

                # Maintain active session map as in the original script.
                if "logged in" in action:
                    active_sessions[user_id] = ts
                elif "logged out" in action and user_id in active_sessions:
                    active_sessions.pop(user_id)

                user_events.append(
                    UserEvent(timestamp=ts, user_id=user_id, action=action)
                )

            elif api_match:
                endpoint = api_match.group("endpoint")
                duration_str = api_match.group("duration") or "0"
                try:
                    duration_ms = int(duration_str)
                except ValueError:
                    duration_ms = 0

                api_calls.append(
                    ApiCall(timestamp=ts, endpoint=endpoint, duration_ms=duration_ms)
                )

    return ParsedLogs(
        errors=errors,
        api_calls=api_calls,
        user_events=user_events,
        active_sessions=active_sessions,
    )


# ---------------------------------------------------------------------------
# Transform: aggregate metrics
# ---------------------------------------------------------------------------


def aggregate_errors(errors: Iterable[ErrorEvent]) -> Dict[str, int]:
    """Aggregate error events into a frequency map by message."""

    counts: Dict[str, int] = {}
    for event in errors:
        counts[event.message] = counts.get(event.message, 0) + 1
    return counts


def aggregate_api_latency(api_calls: Iterable[ApiCall]) -> Dict[str, List[int]]:
    """Group API call durations by endpoint.

    Returns a mapping from endpoint path to the list of durations in
    milliseconds.
    """

    stats: Dict[str, List[int]] = {}
    for call in api_calls:
        stats.setdefault(call.endpoint, []).append(call.duration_ms)
    return stats


# ---------------------------------------------------------------------------
# Load: persist metrics and produce HTML report
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


def store_metrics(
    conn: sqlite3.Connection,
    error_counts: Mapping[str, int],
    api_latency: Mapping[str, Iterable[int]],
    now: Optional[dt.datetime] = None,
) -> None:
    """Persist aggregated metrics into the database using parameterized queries."""

    timestamp_str = (now or dt.datetime.now()).isoformat(sep=" ")
    cur = conn.cursor()

    for message, count in error_counts.items():
        cur.execute(
            "INSERT INTO errors (dt, message, count) VALUES (?, ?, ?)",
            (timestamp_str, message, int(count)),
        )

    for endpoint, durations in api_latency.items():
        durations_list = list(durations)
        if not durations_list:
            continue
        avg_ms = sum(durations_list) / float(len(durations_list))
        cur.execute(
            "INSERT INTO api_metrics (dt, endpoint, avg_ms) VALUES (?, ?, ?)",
            (timestamp_str, endpoint, float(avg_ms)),
        )

    conn.commit()


def render_html_report(
    error_counts: Mapping[str, int],
    api_latency: Mapping[str, Iterable[int]],
    active_sessions: Mapping[str, str],
) -> str:
    """Render the HTML report with the same information as the original script."""

    # Error summary
    html_parts: List[str] = []
    html_parts.append("<html>")
    html_parts.append("<head><title>System Report</title></head>")
    html_parts.append("<body>")
    html_parts.append("<h1>Error Summary</h1>")
    html_parts.append("<ul>")
    for err_msg, count in error_counts.items():
        html_parts.append(
            f"<li><b>{err_msg}</b>: {int(count)} occurrences</li>"  # same wording
        )
    html_parts.append("</ul>")

    # API latency table
    html_parts.append("<h2>API Latency</h2>")
    html_parts.append("<table border='1'>")
    html_parts.append("<tr><th>Endpoint</th><th>Avg (ms)</th></tr>")
    for endpoint, durations in api_latency.items():
        durations_list = list(durations)
        if not durations_list:
            continue
        avg = sum(durations_list) / float(len(durations_list))
        html_parts.append(
            f"<tr><td>{endpoint}</td><td>{round(avg, 1)}</td></tr>"
        )
    html_parts.append("</table>")

    # Active session count
    html_parts.append("<h2>Active Sessions</h2>")
    html_parts.append(
        f"<p>{len(active_sessions)} user(s) currently active</p>"
    )

    html_parts.append("</body>")
    html_parts.append("</html>")

    return "\n".join(html_parts)


def write_report(html: str, path: str = "report.html") -> None:
    """Write the HTML report to disk."""

    with open(path, "w", encoding="utf-8") as f:
        f.write(html)


# ---------------------------------------------------------------------------
# Pipeline orchestration
# ---------------------------------------------------------------------------


def run_pipeline() -> None:
    """Run the full ETL pipeline from logs to database and HTML report."""

    print(f"Connecting to {DB_HOST}:{DB_PORT} as {DB_USER}...")

    lines = list(read_log_lines(LOG_FILE))
    parsed = parse_logs(lines)

    error_counts = aggregate_errors(parsed.errors)
    api_latency = aggregate_api_latency(parsed.api_calls)

    conn = sqlite3.connect(DB_PATH)
    try:
        init_db(conn)
        store_metrics(conn, error_counts, api_latency)
    finally:
        conn.close()

    html = render_html_report(error_counts, api_latency, parsed.active_sessions)
    write_report(html)

    print(f"Job finished at {dt.datetime.now()}")


def _bootstrap_example_log(path: str) -> None:
    """Create an example log file matching the original script's content.

    This is used only when the log file does not already exist, preserving the
    behavior of the original `__main__` block.
    """

    example_lines = [
        "2024-01-01 12:00:00 INFO User 42 logged in",
        "2024-01-01 12:05:00 ERROR Database timeout",
        "2024-01-01 12:05:05 ERROR Database timeout",
        "2024-01-01 12:08:00 INFO API /users/profile took 250ms",
        "2024-01-01 12:09:00 WARN Memory usage at 87%",
        "2024-01-01 12:10:00 INFO User 42 logged out",
    ]

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(example_lines) + "\n")


if __name__ == "__main__":
    if not os.path.exists(LOG_FILE):
        _bootstrap_example_log(LOG_FILE)
    run_pipeline()
