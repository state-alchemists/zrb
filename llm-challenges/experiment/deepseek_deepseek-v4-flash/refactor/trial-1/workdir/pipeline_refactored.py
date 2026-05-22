"""
Server log processing pipeline.

Extracts structured data from server logs, transforms it into summaries
(error counts, API latency stats, active sessions), loads results into
SQLite, and generates an HTML report.

Environment variables:
    PIPELINE_DB_PATH   — SQLite database path (default: metrics.db)
    PIPELINE_LOG_FILE  — Server log file path (default: server.log)
    PIPELINE_DB_HOST   — Unused, preserved for compatibility (default: localhost)
    PIPELINE_DB_PORT   — Unused, preserved for compatibility (default: 5432)
    PIPELINE_DB_USER   — Unused, preserved for compatibility (default: admin)
    PIPELINE_DB_PASS   — Unused, preserved for compatibility (default: password123)
"""

import datetime
import os
import re
import sqlite3
from dataclasses import dataclass
from typing import Optional


# ---------------------------------------------------------------------------
# Configuration (all from environment variables)
# ---------------------------------------------------------------------------

DB_PATH = os.environ.get("PIPELINE_DB_PATH", "metrics.db")
LOG_FILE = os.environ.get("PIPELINE_LOG_FILE", "server.log")
# Preserved for interface compatibility — unused by the local SQLite pipeline.
DB_HOST = os.environ.get("PIPELINE_DB_HOST", "localhost")
DB_PORT = int(os.environ.get("PIPELINE_DB_PORT", "5432"))
DB_USER = os.environ.get("PIPELINE_DB_USER", "admin")
DB_PASS = os.environ.get("PIPELINE_DB_PASS", "password123")


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class LogEntry:
    """A single parsed log line with typed fields per log level.

    Only the fields relevant to the entry's level are populated; the rest
    remain ``None``.
    """

    timestamp: str
    level: str  # "ERR" | "WARN" | "USR" | "API"
    message: Optional[str] = None
    user_id: Optional[str] = None
    action: Optional[str] = None
    endpoint: Optional[str] = None
    duration_ms: Optional[int] = None


# ---------------------------------------------------------------------------
# Regex patterns for log line parsing
# ---------------------------------------------------------------------------

_PATTERN_ERROR = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) ERROR (?P<msg>.+)$"
)
_PATTERN_WARN = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) WARN (?P<msg>.+)$"
)
_PATTERN_USER = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) INFO User (?P<uid>\S+) (?P<action>.+)$"
)
_PATTERN_API = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) INFO API (?P<endpoint>\S+?)(?: took (?P<dur>\d+)ms)?$"
)


# ---------------------------------------------------------------------------
# Extract phase
# ---------------------------------------------------------------------------

def parse_log_file(filepath: str) -> list[LogEntry]:
    """Read and parse every line of the log file into ``LogEntry`` objects.

    Returns an empty list if the file does not exist.
    """
    entries: list[LogEntry] = []
    try:
        with open(filepath, "r") as f:
            for line in f:
                entry = _parse_line(line)
                if entry is not None:
                    entries.append(entry)
    except FileNotFoundError:
        pass
    return entries


def _parse_line(line: str) -> Optional[LogEntry]:
    """Parse a single log line into a ``LogEntry``, or return ``None``."""
    line = line.rstrip("\n")
    m = _PATTERN_ERROR.match(line)
    if m:
        return LogEntry(
            timestamp=m.group("ts"), level="ERR", message=m.group("msg")
        )
    m = _PATTERN_WARN.match(line)
    if m:
        return LogEntry(
            timestamp=m.group("ts"), level="WARN", message=m.group("msg")
        )
    m = _PATTERN_USER.match(line)
    if m:
        return LogEntry(
            timestamp=m.group("ts"),
            level="USR",
            user_id=m.group("uid"),
            action=m.group("action"),
        )
    m = _PATTERN_API.match(line)
    if m:
        dur_str = m.group("dur")
        return LogEntry(
            timestamp=m.group("ts"),
            level="API",
            endpoint=m.group("endpoint"),
            duration_ms=int(dur_str) if dur_str else 0,
        )
    return None


def track_active_sessions(entries: list[LogEntry]) -> set[str]:
    """Replay login/logout events to determine currently active user sessions.

    A session begins at the first ``logged in`` event for a user and ends
    at the first subsequent ``logged out`` event.
    """
    logins: dict[str, str] = {}
    for entry in entries:
        if entry.level != "USR" or entry.user_id is None or entry.action is None:
            continue
        if "logged in" in entry.action:
            logins[entry.user_id] = entry.timestamp
        elif "logged out" in entry.action and entry.user_id in logins:
            del logins[entry.user_id]
    return set(logins.keys())


# ---------------------------------------------------------------------------
# Transform phase
# ---------------------------------------------------------------------------

def summarize_errors(entries: list[LogEntry]) -> dict[str, int]:
    """Count occurrences of each unique error message."""
    counts: dict[str, int] = {}
    for entry in entries:
        if entry.level == "ERR" and entry.message is not None:
            counts[entry.message] = counts.get(entry.message, 0) + 1
    return counts


def aggregate_api_latency(entries: list[LogEntry]) -> dict[str, list[int]]:
    """Group API call durations by endpoint."""
    stats: dict[str, list[int]] = {}
    for entry in entries:
        if entry.level == "API" and entry.endpoint is not None:
            stats.setdefault(entry.endpoint, []).append(entry.duration_ms or 0)
    return stats


# ---------------------------------------------------------------------------
# Load phase  (parameterised queries — no injection risk)
# ---------------------------------------------------------------------------

def init_db(db_path: str) -> sqlite3.Connection:
    """Open a SQLite connection and ensure required tables exist.

    Tables created:
        - ``errors`` (dt, message, count)
        - ``api_metrics`` (dt, endpoint, avg_ms)
    """
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


def insert_error_summaries(
    conn: sqlite3.Connection, summaries: dict[str, int], /
) -> None:
    """Write error summaries to the ``errors`` table.

    Uses parameterised ``executemany`` — safe from SQL injection.
    """
    now = str(datetime.datetime.now())
    conn.executemany(
        "INSERT INTO errors (dt, message, count) VALUES (?, ?, ?)",
        [(now, msg, cnt) for msg, cnt in summaries.items()],
    )


def insert_api_metrics(
    conn: sqlite3.Connection, endpoint_stats: dict[str, list[int]], /
) -> None:
    """Write per-endpoint average latency to the ``api_metrics`` table.

    Uses parameterised ``executemany`` — safe from SQL injection.
    """
    now = str(datetime.datetime.now())
    rows = [
        (now, ep, sum(times) / len(times))
        for ep, times in endpoint_stats.items()
    ]
    conn.executemany(
        "INSERT INTO api_metrics (dt, endpoint, avg_ms) VALUES (?, ?, ?)",
        rows,
    )


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def generate_html_report(
    error_summaries: dict[str, int],
    endpoint_stats: dict[str, list[int]],
    active_session_count: int,
) -> str:
    """Build an HTML report string.

    Sections:
        1. Error summary — bullet list of unique errors with occurrence counts
        2. API latency  — table of endpoints vs average response time (ms)
        3. Active sessions — paragraph with current user count
    """
    lines: list[str] = [
        "<html>\n<head><title>System Report</title></head>\n<body>",
        "<h1>Error Summary</h1>\n<ul>",
    ]
    for msg, count in error_summaries.items():
        lines.append(f"<li><b>{msg}</b>: {count} occurrences</li>")
    lines.append("</ul>")

    lines.append("<h2>API Latency</h2>\n<table border='1'>")
    lines.append("<tr><th>Endpoint</th><th>Avg (ms)</th></tr>")
    for ep, times in endpoint_stats.items():
        avg = sum(times) / len(times)
        lines.append(f"<tr><td>{ep}</td><td>{round(avg, 1)}</td></tr>")
    lines.append("</table>")

    lines.append("<h2>Active Sessions</h2>")
    lines.append(f"<p>{active_session_count} user(s) currently active</p>")
    lines.append("</body>\n</html>")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def main() -> None:
    """Run the full ETL pipeline and write ``report.html``."""
    print(f"Reading log file: {LOG_FILE}")
    print(f"Connecting to {DB_HOST}:{DB_PORT} as {DB_USER}...")

    # Extract
    entries = parse_log_file(LOG_FILE)
    active_sessions = track_active_sessions(entries)

    # Load (DB)
    conn = init_db(DB_PATH)
    try:
        # Transform + Load
        error_summaries = summarize_errors(entries)
        insert_error_summaries(conn, error_summaries)

        endpoint_stats = aggregate_api_latency(entries)
        insert_api_metrics(conn, endpoint_stats)

        conn.commit()
    finally:
        conn.close()

    # Report
    html = generate_html_report(
        error_summaries, endpoint_stats, len(active_sessions),
    )
    with open("report.html", "w") as f:
        f.write(html)

    print(f"Job finished at {datetime.datetime.now()}")


if __name__ == "__main__":
    # Seed sample data when the log file doesn't exist yet.
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, "w") as f:
            f.write("2024-01-01 12:00:00 INFO User 42 logged in\n")
            f.write("2024-01-01 12:05:00 ERROR Database timeout\n")
            f.write("2024-01-01 12:05:05 ERROR Database timeout\n")
            f.write("2024-01-01 12:08:00 INFO API /users/profile took 250ms\n")
            f.write("2024-01-01 12:09:00 WARN Memory usage at 87%\n")
            f.write("2024-01-01 12:10:00 INFO User 42 logged out\n")
    main()
