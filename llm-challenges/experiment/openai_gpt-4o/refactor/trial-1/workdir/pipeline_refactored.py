"""Refactored server-log pipeline: Extract → Transform → Load.

Reads a server log file, parses it with regex, aggregates errors and API
latency metrics, persists to SQLite with parameterized queries, and writes
an HTML report.
"""

from __future__ import annotations

import datetime
import os
import re
import sqlite3
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_DEFAULT_DB_PATH = "metrics.db"
_DEFAULT_LOG_PATH = "server.log"


def _get_config() -> Tuple[str, str]:
    """Read configuration from environment variables with sensible defaults.

    Returns:
        A tuple of (db_path, log_file_path).
    """
    return (
        os.environ.get("METRICS_DB_PATH", _DEFAULT_DB_PATH),
        os.environ.get("SERVER_LOG_PATH", _DEFAULT_LOG_PATH),
    )


# ---------------------------------------------------------------------------
# Extract — parse raw log lines into structured data
# ---------------------------------------------------------------------------

_TIMESTAMP = r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}"

_RE_ERROR = re.compile(rf"^({_TIMESTAMP}) ERROR (.+)$")
_RE_WARN = re.compile(rf"^({_TIMESTAMP}) WARN (.+)$")
_RE_USER = re.compile(rf"^({_TIMESTAMP}) INFO User (\d+) (logged in|logged out)$")
_RE_API = re.compile(rf"^({_TIMESTAMP}) INFO API (/\S+) took (\d+)ms$")


@dataclass
class LogEntry:
    """A single parsed log entry with type-discriminated optional fields."""

    timestamp: str
    entry_type: str  # "ERROR" | "WARN" | "USER" | "API"
    message: Optional[str] = None
    user_id: Optional[str] = None
    action: Optional[str] = None
    endpoint: Optional[str] = None
    duration_ms: Optional[int] = None


def parse_log_line(line: str) -> Optional[LogEntry]:
    """Parse one log line into a LogEntry, or return None if unmatched.

    Supported formats (all start with ``YYYY-MM-DD HH:MM:SS``):

    - ``... ERROR <message>``
    - ``... WARN <message>``
    - ``... INFO User <id> logged in|logged out``
    - ``... INFO API <endpoint> took <ms>ms``

    Args:
        line: A single line from the server log file.

    Returns:
        A LogEntry if the line matches a known pattern, otherwise None.
    """
    m = _RE_ERROR.match(line)
    if m:
        return LogEntry(timestamp=m.group(1), entry_type="ERROR", message=m.group(2))

    m = _RE_WARN.match(line)
    if m:
        return LogEntry(timestamp=m.group(1), entry_type="WARN", message=m.group(2))

    m = _RE_USER.match(line)
    if m:
        return LogEntry(
            timestamp=m.group(1),
            entry_type="USER",
            user_id=m.group(2),
            action=m.group(3),
        )

    m = _RE_API.match(line)
    if m:
        return LogEntry(
            timestamp=m.group(1),
            entry_type="API",
            endpoint=m.group(2),
            duration_ms=int(m.group(3)),
        )

    return None


def extract_logs(log_path: str) -> List[LogEntry]:
    """Read a log file and parse every line into a LogEntry.

    Skips blank lines and lines that don't match any known pattern.

    Args:
        log_path: Path to the server log file.

    Returns:
        A list of parsed LogEntry objects in file order.
    """
    entries: List[LogEntry] = []
    if not os.path.exists(log_path):
        return entries

    with open(log_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            entry = parse_log_line(line)
            if entry is not None:
                entries.append(entry)

    return entries


# ---------------------------------------------------------------------------
# Transform — aggregate parsed data into summaries
# ---------------------------------------------------------------------------


def summarize_errors(entries: List[LogEntry]) -> Dict[str, int]:
    """Count occurrences of each distinct error message.

    Args:
        entries: All parsed log entries.

    Returns:
        A dict mapping error message text to its occurrence count.
    """
    counts: Dict[str, int] = {}
    for e in entries:
        if e.entry_type == "ERROR" and e.message is not None:
            counts[e.message] = counts.get(e.message, 0) + 1
    return counts


def compute_api_latency(entries: List[LogEntry]) -> Dict[str, List[int]]:
    """Group API call durations by endpoint.

    Args:
        entries: All parsed log entries.

    Returns:
        A dict mapping endpoint path to a list of observed durations in ms.
    """
    stats: Dict[str, List[int]] = defaultdict(list)
    for e in entries:
        if e.entry_type == "API" and e.endpoint is not None and e.duration_ms is not None:
            stats[e.endpoint].append(e.duration_ms)
    return dict(stats)


def track_active_sessions(entries: List[LogEntry]) -> Set[str]:
    """Determine currently active user sessions from login/logout events.

    Args:
        entries: All parsed log entries.

    Returns:
        A set of user IDs with active (not yet logged-out) sessions.
    """
    sessions: Dict[str, str] = {}
    for e in entries:
        if e.entry_type == "USER" and e.user_id is not None and e.action is not None:
            if e.action == "logged in":
                sessions[e.user_id] = e.timestamp
            elif e.action == "logged out":
                sessions.pop(e.user_id, None)
    return set(sessions.keys())


# ---------------------------------------------------------------------------
# Load — persist to database and write HTML report
# ---------------------------------------------------------------------------


def init_db(conn: sqlite3.Connection) -> None:
    """Create database tables if they don't already exist.

    Args:
        conn: An open SQLite connection.
    """
    conn.execute(
        "CREATE TABLE IF NOT EXISTS errors (dt TEXT, message TEXT, count INTEGER)"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS api_metrics (dt TEXT, endpoint TEXT, avg_ms REAL)"
    )
    conn.commit()


def load_error_summary(
    conn: sqlite3.Connection, errors: Dict[str, int], timestamp: str
) -> None:
    """Insert error summary rows using a parameterized query.

    Args:
        conn: An open SQLite connection.
        errors: Dict of error message to occurrence count.
        timestamp: ISO-formatted timestamp for the batch.
    """
    for msg, count in errors.items():
        conn.execute(
            "INSERT INTO errors (dt, message, count) VALUES (?, ?, ?)",
            (timestamp, msg, count),
        )
    conn.commit()


def load_api_metrics(
    conn: sqlite3.Connection, api_stats: Dict[str, List[int]], timestamp: str
) -> None:
    """Insert API latency summary rows using a parameterized query.

    Args:
        conn: An open SQLite connection.
        api_stats: Dict of endpoint to list of observed durations (ms).
        timestamp: ISO-formatted timestamp for the batch.
    """
    for endpoint, times in api_stats.items():
        avg_ms = sum(times) / len(times)
        conn.execute(
            "INSERT INTO api_metrics (dt, endpoint, avg_ms) VALUES (?, ?, ?)",
            (timestamp, endpoint, avg_ms),
        )
    conn.commit()


def generate_html_report(
    errors: Dict[str, int],
    api_stats: Dict[str, List[int]],
    active_sessions: int,
) -> str:
    """Build an HTML string summarising errors, API latency, and sessions.

    Args:
        errors: Dict of error message to occurrence count.
        api_stats: Dict of endpoint to list of observed durations (ms).
        active_sessions: Number of currently active user sessions.

    Returns:
        A complete HTML document as a string.
    """
    rows = "".join(
        f"<li><b>{msg}</b>: {count} occurrences</li>\n"
        for msg, count in sorted(errors.items(), key=lambda x: -x[1])
    )

    avg_ms_for_display = {
        ep: sum(times) / len(times) for ep, times in api_stats.items()
    }
    table_rows = "".join(
        f"<tr><td>{ep}</td><td>{round(avg, 1)}</td></tr>\n"
        for ep, avg in sorted(avg_ms_for_display.items())
    )

    return (
        "<html>\n"
        "<head><title>System Report</title></head>\n"
        "<body>\n"
        "<h1>Error Summary</h1>\n"
        "<ul>\n"
        f"{rows}"
        "</ul>\n"
        "<h2>API Latency</h2>\n"
        "<table border='1'>\n"
        "<tr><th>Endpoint</th><th>Avg (ms)</th></tr>\n"
        f"{table_rows}"
        "</table>\n"
        "<h2>Active Sessions</h2>\n"
        f"<p>{active_sessions} user(s) currently active</p>\n"
        "</body>\n"
        "</html>"
    )


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def main() -> None:
    """Run the full pipeline: extract logs, transform, and load results."""
    db_path, log_path = _get_config()

    _seed_demo_data_if_empty(log_path)

    now = datetime.datetime.now().isoformat()
    print(f"Pipeline starting at {now}")

    # Extract
    entries = extract_logs(log_path)
    print(f"  Parsed {len(entries)} log entries")

    # Transform
    error_summary = summarize_errors(entries)
    api_stats = compute_api_latency(entries)
    active_sessions = track_active_sessions(entries)
    print(
        f"  Found {sum(error_summary.values())} errors across "
        f"{len(error_summary)} distinct messages"
    )
    print(f"  Endpoints tracked: {list(api_stats.keys())}")
    print(f"  Active sessions: {len(active_sessions)}")

    # Load — DB
    conn = sqlite3.connect(db_path)
    try:
        init_db(conn)
        load_error_summary(conn, error_summary, now)
        load_api_metrics(conn, api_stats, now)
    finally:
        conn.close()

    # Load — report
    report = generate_html_report(error_summary, api_stats, len(active_sessions))
    with open("report.html", "w") as f:
        f.write(report)

    finish = datetime.datetime.now()
    print(f"Pipeline finished at {finish.isoformat()}")
    print("report.html written.")


def _seed_demo_data_if_empty(log_path: str) -> None:
    """Write sample log lines if the log file doesn't exist yet."""
    if os.path.exists(log_path):
        return
    lines = [
        "2024-01-01 12:00:00 INFO User 42 logged in\n",
        "2024-01-01 12:05:00 ERROR Database timeout\n",
        "2024-01-01 12:05:05 ERROR Database timeout\n",
        "2024-01-01 12:08:00 INFO API /users/profile took 250ms\n",
        "2024-01-01 12:09:00 WARN Memory usage at 87%\n",
        "2024-01-01 12:10:00 INFO User 42 logged out\n",
    ]
    with open(log_path, "w") as f:
        f.writelines(lines)
    print(f"  Seeded demo data → {log_path}")


if __name__ == "__main__":
    main()
