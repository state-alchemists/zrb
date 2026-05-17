"""
Server log processing pipeline.

Extracts metrics from server logs, stores them in a database, and generates an HTML report.
"""
from __future__ import annotations

import os
import re
import sqlite3
import html
from datetime import datetime
from typing import NamedTuple


# ---------------------------------------------------------------------------
# Configuration (from environment variables with sensible defaults for dev)
# ---------------------------------------------------------------------------

DB_PATH: str = os.environ.get("DB_PATH", "metrics.db")
LOG_FILE: str = os.environ.get("LOG_FILE", "server.log")
DB_HOST: str = os.environ.get("DB_HOST", "localhost")
DB_PORT: int = int(os.environ.get("DB_PORT", "5432"))
DB_USER: str = os.environ.get("DB_USER", "")
DB_PASS: str = os.environ.get("DB_PASS", "")


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

class LogEntry(NamedTuple):
    """Structured log record."""
    timestamp: str
    level: str
    message: str


class SessionEvent(NamedTuple):
    """User session event extracted from log."""
    timestamp: str
    user_id: str
    action: str  # "logged in" or "logged out"


class ApiCall(NamedTuple):
    """API call record with latency."""
    timestamp: str
    endpoint: str
    duration_ms: int


class ErrorCount(NamedTuple):
    """Aggregated error bucket."""
    message: str
    count: int


class EndpointStats(NamedTuple):
    """Aggregated API latency per endpoint."""
    endpoint: str
    avg_ms: float


# ---------------------------------------------------------------------------
# EXTRACT — parse log file into structured records
# ---------------------------------------------------------------------------

LOG_PATTERN = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) "
    r"(?P<level>ERROR|INFO|WARN)\s+"
    r"(?P<rest>.*)"
)

USER_SESSION_PATTERN = re.compile(
    r"^User (?P<user_id>\S+)\s+(?P<action>logged in|logged out)"
)

API_CALL_PATTERN = re.compile(
    r"^API (?P<endpoint>\S+)\s+took\s+(?P<duration>\d+)ms"
)


def extract_log_entries(log_path: str) -> list[LogEntry]:
    """
    Parse a text-mode log file and return a list of structured LogEntry records.

    Skips lines that don't match the expected format rather than raising.
    """
    entries: list[LogEntry] = []
    if not os.path.exists(log_path):
        return entries

    with open(log_path, "r") as f:
        for line in f:
            line = line.rstrip("\n")
            m = LOG_PATTERN.match(line)
            if not m:
                continue
            entries.append(LogEntry(
                timestamp=m.group("timestamp"),
                level=m.group("level"),
                message=m.group("rest").strip(),
            ))
    return entries


def extract_session_events(entries: list[LogEntry]) -> list[SessionEvent]:
    """Filter INFO entries that represent user session events."""
    events: list[SessionEvent] = []
    for e in entries:
        if e.level != "INFO" or "User" not in e.message:
            continue
        m = USER_SESSION_PATTERN.search(e.message)
        if not m:
            continue
        events.append(SessionEvent(
            timestamp=e.timestamp,
            user_id=m.group("user_id"),
            action=m.group("action"),
        ))
    return events


def extract_api_calls(entries: list[LogEntry]) -> list[ApiCall]:
    """Filter INFO entries that represent API calls with latency."""
    calls: list[ApiCall] = []
    for e in entries:
        if e.level != "INFO" or "API" not in e.message:
            continue
        m = API_CALL_PATTERN.search(e.message)
        if not m:
            continue
        calls.append(ApiCall(
            timestamp=e.timestamp,
            endpoint=m.group("endpoint"),
            duration_ms=int(m.group("duration")),
        ))
    return calls


def extract_errors(entries: list[LogEntry]) -> list[str]:
    """Filter ERROR-level messages for aggregation."""
    return [e.message for e in entries if e.level == "ERROR"]


# ---------------------------------------------------------------------------
# TRANSFORM — aggregate raw records into summary statistics
# ---------------------------------------------------------------------------

def transform_error_counts(messages: list[str]) -> list[ErrorCount]:
    """
    Count occurrences of each distinct error message.
    Returns a sorted list (most frequent first) for report readability.
    """
    bucket: dict[str, int] = {}
    for msg in messages:
        bucket[msg] = bucket.get(msg, 0) + 1
    return sorted(
        [ErrorCount(msg, count) for msg, count in bucket.items()],
        key=lambda x: x.count,
        reverse=True,
    )


def transform_api_stats(calls: list[ApiCall]) -> list[EndpointStats]:
    """Compute average latency per endpoint across all recorded calls."""
    by_endpoint: dict[str, list[int]] = {}
    for call in calls:
        by_endpoint.setdefault(call.endpoint, []).append(call.duration_ms)

    stats: list[EndpointStats] = []
    for endpoint, durations in by_endpoint.items():
        avg = sum(durations) / len(durations)
        stats.append(EndpointStats(endpoint=endpoint, avg_ms=avg))
    return stats


def transform_active_sessions(events: list[SessionEvent]) -> int:
    """
    Compute the number of currently active sessions.
    A user is active from their "logged in" event until a matching "logged out" event.
    Users with multiple login events before logout are counted once.
    """
    active: set[str] = set()
    for event in events:
        if event.action == "logged in":
            active.add(event.user_id)
        elif event.action == "logged out" and event.user_id in active:
            active.discard(event.user_id)
    return len(active)


# ---------------------------------------------------------------------------
# LOAD — persist to DB and render HTML report
# ---------------------------------------------------------------------------

def ensure_tables(conn: sqlite3.Connection) -> None:
    """Create (or confirm existing) metric tables."""
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS errors (
            dt TEXT,
            message TEXT,
            count INTEGER
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS api_metrics (
            dt TEXT,
            endpoint TEXT,
            avg_ms REAL
        )
    """)


def load_error_counts(
    conn: sqlite3.Connection,
    error_counts: list[ErrorCount],
) -> None:
    """Insert aggregated error counts using a parameterized query."""
    cur = conn.cursor()
    now = datetime.now().isoformat()
    cur.executemany(
        "INSERT INTO errors (dt, message, count) VALUES (?, ?, ?)",
        [(now, ec.message, ec.count) for ec in error_counts],
    )
    conn.commit()


def load_api_stats(
    conn: sqlite3.Connection,
    endpoint_stats: list[EndpointStats],
) -> None:
    """Insert API latency aggregates using a parameterized query."""
    cur = conn.cursor()
    now = datetime.now().isoformat()
    cur.executemany(
        "INSERT INTO api_metrics (dt, endpoint, avg_ms) VALUES (?, ?, ?)",
        [(now, es.endpoint, es.avg_ms) for es in endpoint_stats],
    )
    conn.commit()


def render_html_report(
    error_counts: list[ErrorCount],
    endpoint_stats: list[EndpointStats],
    active_sessions: int,
    output_path: str,
) -> None:
    """
    Render the final HTML report covering error summary, API latency table,
    and active session count.
    """
    # Escape user content to prevent XSS in the report itself
    rows_errors = "".join(
        f"<li><b>{html.escape(ec.message)}</b>: {ec.count} occurrences</li>"
        for ec in error_counts
    )

    rows_api = "".join(
        f"<tr><td>{html.escape(es.endpoint)}</td>"
        f"<td>{round(es.avg_ms, 1)}</td></tr>"
        for es in endpoint_stats
    )

    report = (
        "<html>\n"
        "<head><title>System Report</title></head>\n"
        "<body>\n"
        "<h1>Error Summary</h1>\n"
        f"<ul>\n{rows_errors}</ul>\n"
        "<h2>API Latency</h2>\n"
        "<table border='1'>\n"
        "<tr><th>Endpoint</th><th>Avg (ms)</th></tr>\n"
        f"{rows_api}\n"
        "</table>\n"
        "<h2>Active Sessions</h2>\n"
        f"<p>{active_sessions} user(s) currently active</p>\n"
        "</body>\n</html>"
    )

    with open(output_path, "w") as f:
        f.write(report)


# ---------------------------------------------------------------------------
# Pipeline orchestration
# ---------------------------------------------------------------------------

def run_pipeline(
    log_path: str = LOG_FILE,
    db_path: str = DB_PATH,
    report_path: str = "report.html",
) -> None:
    """
    Execute the full ETL pipeline: extract → transform → load.

    Parameters
    ----------
    log_path : str
        Path to the server log file.
    db_path : str
        Path to the SQLite metrics database.
    report_path : str
        Destination for the HTML report.
    """
    log_info = f"Connecting to {DB_HOST}:{DB_PORT} as {DB_USER}..."
    print(log_info)

    # EXTRACT
    entries = extract_log_entries(log_path)
    session_events = extract_session_events(entries)
    api_calls = extract_api_calls(entries)
    error_messages = extract_errors(entries)

    # TRANSFORM
    error_counts = transform_error_counts(error_messages)
    endpoint_stats = transform_api_stats(api_calls)
    active_sessions = transform_active_sessions(session_events)

    # LOAD
    conn = sqlite3.connect(db_path)
    ensure_tables(conn)
    load_error_counts(conn, error_counts)
    load_api_stats(conn, endpoint_stats)
    conn.close()

    render_html_report(error_counts, endpoint_stats, active_sessions, report_path)
    print(f"Job finished at {datetime.now()}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Create a sample log so the pipeline can run standalone
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, "w") as f:
            f.write("2024-01-01 12:00:00 INFO User 42 logged in\n")
            f.write("2024-01-01 12:05:00 ERROR Database timeout\n")
            f.write("2024-01-01 12:05:05 ERROR Database timeout\n")
            f.write("2024-01-01 12:08:00 INFO API /users/profile took 250ms\n")
            f.write("2024-01-01 12:09:00 WARN Memory usage at 87%\n")
            f.write("2024-01-01 12:10:00 INFO User 42 logged out\n")

    run_pipeline()