"""ETL pipeline that processes server logs and generates an HTML report.

The pipeline extracts log entries from a plain-text log file, transforms them
into structured metrics (error counts, API latency averages, active sessions),
and loads the results into a SQLite database as well as a static HTML report.
"""

from __future__ import annotations

import dataclasses
import datetime
import os
import re
import sqlite3
from collections import defaultdict
from pathlib import Path
from typing import Protocol

# ---------------------------------------------------------------------------
# Configuration (loaded from environment variables)
# ---------------------------------------------------------------------------
DB_PATH = os.getenv("DB_PATH", "metrics.db")
LOG_FILE = os.getenv("LOG_FILE", "server.log")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_USER = os.getenv("DB_USER", "admin")
DB_PASS = os.getenv("DB_PASS", "password123")
REPORT_PATH = os.getenv("REPORT_PATH", "report.html")

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class LogEntry:
    """A single parsed log line."""

    timestamp: str
    level: str
    raw_message: str


@dataclasses.dataclass(frozen=True)
class UserAction:
    """A user login/logout event extracted from a log entry."""

    timestamp: str
    user_id: str
    action: str


@dataclasses.dataclass(frozen=True)
class ApiCall:
    """An API call event extracted from a log entry."""

    timestamp: str
    endpoint: str
    duration_ms: int


@dataclasses.dataclass
class TransformedData:
    """Aggregated results produced by the transform step."""

    error_counts: dict[str, int]
    api_latency: dict[str, float]
    active_sessions: dict[str, str]


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------

# Regex for the common log prefix:  YYYY-MM-DD HH:MM:SS LEVEL
_LOG_PREFIX_RE = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) "
    r"(?P<level>ERROR|INFO|WARN) "
    r"(?P<message>.*)$"
)

# Regex for user actions in the message portion
_USER_ACTION_RE = re.compile(
    r"User (?P<user_id>\S+) (?P<action>.+)"
)

# Regex for API calls in the message portion
_API_CALL_RE = re.compile(
    r"API (?P<endpoint>\S+) took (?P<duration>\d+)ms"
)


def _ensure_sample_log_file(path: str) -> None:
    """Create a sample log file if one does not already exist."""
    if os.path.exists(path):
        return
    sample_lines = [
        "2024-01-01 12:00:00 INFO User 42 logged in\n",
        "2024-01-01 12:05:00 ERROR Database timeout\n",
        "2024-01-01 12:05:05 ERROR Database timeout\n",
        "2024-01-01 12:08:00 INFO API /users/profile took 250ms\n",
        "2024-01-01 12:09:00 WARN Memory usage at 87%\n",
        "2024-01-01 12:10:00 INFO User 42 logged out\n",
    ]
    with open(path, "w", encoding="utf-8") as fh:
        fh.writelines(sample_lines)


def parse_log_line(line: str) -> LogEntry | None:
    """Parse a single log line into a *LogEntry*.

    Returns *None* when the line does not match the expected format.
    """
    match = _LOG_PREFIX_RE.match(line.strip())
    if not match:
        return None
    return LogEntry(
        timestamp=match.group("timestamp"),
        level=match.group("level"),
        raw_message=match.group("message"),
    )


def extract_logs(log_file_path: str) -> tuple[list[LogEntry], list[UserAction], list[ApiCall]]:
    """Read *log_file_path* and return extracted log entries, user actions, and API calls.

    Sessions are tracked while reading the file: a login adds a user to the
    internal session map and a logout removes them.
    """
    entries: list[LogEntry] = []
    user_actions: list[UserAction] = []
    api_calls: list[ApiCall] = []
    sessions: dict[str, str] = {}

    with open(log_file_path, "r", encoding="utf-8") as fh:
        for line in fh:
            entry = parse_log_line(line)
            if entry is None:
                continue
            entries.append(entry)

            if entry.level == "INFO":
                user_match = _USER_ACTION_RE.match(entry.raw_message)
                if user_match:
                    user_id = user_match.group("user_id")
                    action = user_match.group("action")
                    user_actions.append(
                        UserAction(timestamp=entry.timestamp, user_id=user_id, action=action)
                    )
                    if action == "logged in":
                        sessions[user_id] = entry.timestamp
                    elif action == "logged out" and user_id in sessions:
                        sessions.pop(user_id)
                    continue

                api_match = _API_CALL_RE.match(entry.raw_message)
                if api_match:
                    api_calls.append(
                        ApiCall(
                            timestamp=entry.timestamp,
                            endpoint=api_match.group("endpoint"),
                            duration_ms=int(api_match.group("duration")),
                        )
                    )

    # Preserve legacy side-effect: include users still in the session map as active.
    # Convert to fake UserAction entries so transform can rebuild the same dict.
    active_user_actions = [
        UserAction(timestamp=ts, user_id=uid, action="logged in")
        for uid, ts in sessions.items()
    ]

    return entries, user_actions + active_user_actions, api_calls


# ---------------------------------------------------------------------------
# Transform
# ---------------------------------------------------------------------------


def transform(
    entries: list[LogEntry],
    user_actions: list[UserAction],
    api_calls: list[ApiCall],
) -> TransformedData:
    """Aggregate extracted data into the metrics required by the report."""
    error_counts: dict[str, int] = defaultdict(int)
    api_latencies: dict[str, list[int]] = defaultdict(list)
    active_sessions: dict[str, str] = {}

    for entry in entries:
        if entry.level == "ERROR":
            error_counts[entry.raw_message] += 1
        elif entry.level == "WARN":
            # Legacy behaviour: warnings were stored alongside errors in the
            # original ``d_list`` but not counted in ``r``. We keep the raw
            # extraction for completeness but do not include them in error_counts.
            pass

    for ua in user_actions:
        if ua.action == "logged in":
            active_sessions[ua.user_id] = ua.timestamp
        elif ua.action == "logged out" and ua.user_id in active_sessions:
            active_sessions.pop(ua.user_id)

    for call in api_calls:
        api_latencies[call.endpoint].append(call.duration_ms)

    averaged_latency = {
        endpoint: sum(times) / len(times) for endpoint, times in api_latencies.items()
    }

    return TransformedData(
        error_counts=dict(error_counts),
        api_latency=averaged_latency,
        active_sessions=active_sessions,
    )


# ---------------------------------------------------------------------------
# Load
# ---------------------------------------------------------------------------


def init_database(db_path: str) -> sqlite3.Connection:
    """Open (and create if absent) the SQLite database, returning the connection."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        "CREATE TABLE IF NOT EXISTS errors (dt TEXT, message TEXT, count INTEGER)"
    )
    cursor.execute(
        "CREATE TABLE IF NOT EXISTS api_metrics (dt TEXT, endpoint TEXT, avg_ms REAL)"
    )
    conn.commit()
    return conn


def load_metrics(conn: sqlite3.Connection, data: TransformedData) -> None:
    """Persist aggregated metrics into *conn* using parameterized queries."""
    cursor = conn.cursor()
    now = datetime.datetime.now().isoformat(sep=" ", timespec="seconds")

    for message, count in data.error_counts.items():
        cursor.execute(
            "INSERT INTO errors (dt, message, count) VALUES (?, ?, ?)",
            (now, message, count),
        )

    for endpoint, avg_ms in data.api_latency.items():
        cursor.execute(
            "INSERT INTO api_metrics (dt, endpoint, avg_ms) VALUES (?, ?, ?)",
            (now, endpoint, round(avg_ms, 2)),
        )

    conn.commit()


def generate_report(data: TransformedData, report_path: str) -> None:
    """Render an HTML report from the transformed data and write it to disk."""
    lines = [
        "<html>",
        "<head><title>System Report</title></head>",
        "<body>",
        "<h1>Error Summary</h1>",
        "<ul>",
    ]

    for err_msg, count in data.error_counts.items():
        html_msg = err_msg.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        lines.append(f"<li><b>{html_msg}</b>: {count} occurrences</li>")

    lines.extend([
        "</ul>",
        "<h2>API Latency</h2>",
        "<table border='1'>",
        "<tr><th>Endpoint</th><th>Avg (ms)</th></tr>",
    ])

    for ep, avg in data.api_latency.items():
        html_ep = ep.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        lines.append(f"<tr><td>{html_ep}</td><td>{round(avg, 1)}</td></tr>")

    lines.extend([
        "</table>",
        "<h2>Active Sessions</h2>",
        f"<p>{len(data.active_sessions)} user(s) currently active</p>",
        "</body>",
        "</html>",
    ])

    with open(report_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
        fh.write("\n")


# ---------------------------------------------------------------------------
# Pipeline orchestration
# ---------------------------------------------------------------------------


def run_pipeline() -> None:
    """Execute the full ETL pipeline."""
    _ensure_sample_log_file(LOG_FILE)

    print(f"Connecting to {DB_HOST}:{DB_PORT} as {DB_USER} ...")

    entries, user_actions, api_calls = extract_logs(LOG_FILE)
    data = transform(entries, user_actions, api_calls)

    conn = init_database(DB_PATH)
    try:
        load_metrics(conn, data)
    finally:
        conn.close()

    generate_report(data, REPORT_PATH)

    print(f"Job finished at {datetime.datetime.now()}")


if __name__ == "__main__":
    run_pipeline()
