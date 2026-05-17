"""
pipeline_refactored.py — Log processing pipeline with proper ETL separation.

Extracts data from server logs using regex, transforms into structured records,
and loads results into both SQLite (for persistence) and an HTML report.

Environment variables (all optional with sensible defaults):
    LOG_FILE_PATH    — path to the server log file  (default: server.log)
    DB_PATH          — path to the SQLite database   (default: metrics.db)
    DB_HOST          — ignored (SQLite local); retained for config parity
    DB_PORT          — ignored
    DB_USER          — ignored
    DB_PASS          — ignored
"""

from __future__ import annotations

import datetime
import os
import re
import sqlite3
from collections import Counter, defaultdict
from typing import Any

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

LOG_FILE_PATH: str = os.environ.get("LOG_FILE_PATH", "server.log")
DB_PATH: str = os.environ.get("DB_PATH", "metrics.db")
# Retained for config parity — the original script referenced these even though
# only SQLite was used.  They are unused by the refactored pipeline.
DB_HOST: str = os.environ.get("DB_HOST", "localhost")
DB_PORT: str = os.environ.get("DB_PORT", "5432")
DB_USER: str = os.environ.get("DB_USER", "admin")
DB_PASS: str = os.environ.get("DB_PASS", "password123")

# ---------------------------------------------------------------------------
# Regex patterns for log-line parsing
# ---------------------------------------------------------------------------

# Common prefix:  <date> <time> <LEVEL>
_PREFIX_RE = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s+"
    r"(?P<level>ERROR|WARN|INFO)\s+"
    r"(?P<rest>.*)$"
)

# ERROR: everything after the level is the message
# WARN:  everything after the level is the message
# INFO User <id> <action>
_INFO_USER_RE = re.compile(
    r"^User\s+(?P<user_id>\S+)\s+(?P<action>.+)$"
)
# INFO API <endpoint> took <duration>ms
_INFO_API_RE = re.compile(
    r"^API\s+(?P<endpoint>\S+)\s+took\s+(?P<duration_ms>\d+)ms$"
)


# ---------------------------------------------------------------------------
# Data types (simple TypedDict-like stubs; plain dicts for Python 3.8 compat)
# ---------------------------------------------------------------------------

LogEvent = dict[str, Any]
"""Parsed log event with at least keys: timestamp, level, type, raw."""


# ---------------------------------------------------------------------------
# Extract
# ---------------------------------------------------------------------------

def read_log_file(path: str) -> list[str]:
    """Read all lines from *path*.  Returns [] when the file does not exist."""
    if not os.path.exists(path):
        print(f"[WARN] Log file not found: {path}")
        return []
    with open(path, "r") as f:
        return f.readlines()


def parse_log_line(line: str) -> LogEvent | None:
    """Parse a single log line into a structured dict, or None if unparseable.

    Recognised line types:

        <ts> ERROR <message>
        <ts> WARN  <message>
        <ts> INFO  User <id> logged in / logged out / <action>
        <ts> INFO  API <endpoint> took <duration>ms
    """
    m = _PREFIX_RE.match(line)
    if not m:
        return None

    ts = m.group("timestamp")
    level = m.group("level")
    rest = m.group("rest")

    event: LogEvent = {
        "timestamp": ts,
        "level": level,
        "raw": line.strip(),
    }

    if level in ("ERROR", "WARN"):
        event["type"] = level          # "ERROR" or "WARN"
        event["message"] = rest.strip()
        return event

    # INFO — sub-type detection
    user_m = _INFO_USER_RE.match(rest)
    if user_m:
        event["type"] = "USER"
        event["user_id"] = user_m.group("user_id")
        event["action"] = user_m.group("action")
        return event

    api_m = _INFO_API_RE.match(rest)
    if api_m:
        event["type"] = "API"
        event["endpoint"] = api_m.group("endpoint")
        event["duration_ms"] = int(api_m.group("duration_ms"))
        return event

    # Fallback: treat as generic INFO
    event["type"] = "INFO"
    event["message"] = rest.strip()
    return event


def extract(path: str) -> list[LogEvent]:
    """Read and parse every line in the log file.  Unparseable lines are skipped."""
    return [
        event
        for line in read_log_file(path)
        if (event := parse_log_line(line)) is not None
    ]


# ---------------------------------------------------------------------------
# Transform
# ---------------------------------------------------------------------------

Summary = dict[str, Any]
"""
Keys produced by ``transform``:

    error_counts     Counter[str]     — error message → occurrence count
    api_latency      dict[str, float] — endpoint    → avg duration (ms)
    active_sessions  int              — users currently logged in
    events           list[LogEvent]   — full event list (pass-through for DB)
"""


def _build_error_counts(events: list[LogEvent]) -> Counter[str]:
    """Count occurrences of each unique ERROR message."""
    return Counter(
        e["message"]
        for e in events
        if e.get("type") == "ERROR"
    )


def _build_api_latency(events: list[LogEvent]) -> dict[str, float]:
    """Compute average latency (ms) per API endpoint."""
    durations: dict[str, list[int]] = defaultdict(list)
    for e in events:
        if e.get("type") == "API":
            durations[e["endpoint"]].append(e["duration_ms"])
    return {
        ep: sum(vals) / len(vals)
        for ep, vals in durations.items()
    }


def _count_active_sessions(events: list[LogEvent]) -> int:
    """Determine the number of users still logged in at the end of the log.

    Processes events in chronological order, tracking login/logout per user.
    """
    sessions: dict[str, str] = {}  # user_id → login_timestamp
    for e in events:
        if e.get("type") != "USER":
            continue
        uid = e["user_id"]
        action = e["action"]
        if "logged in" in action:
            sessions[uid] = e["timestamp"]
        elif "logged out" in action and uid in sessions:
            del sessions[uid]
    return len(sessions)


def transform(events: list[LogEvent]) -> Summary:
    """Derive summary statistics from the raw event list."""
    return {
        "error_counts": _build_error_counts(events),
        "api_latency": _build_api_latency(events),
        "active_sessions": _count_active_sessions(events),
        "events": events,
    }


# ---------------------------------------------------------------------------
# Load
# ---------------------------------------------------------------------------

def _init_db(db_path: str) -> sqlite3.Connection:
    """Open (or create) the SQLite database and ensure tables exist."""
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


def _load_errors(conn: sqlite3.Connection, error_counts: Counter[str]) -> None:
    """Insert aggregated error counts via parameterised query."""
    now = datetime.datetime.now().isoformat()
    conn.executemany(
        "INSERT INTO errors (dt, message, count) VALUES (?, ?, ?)",
        [(now, msg, cnt) for msg, cnt in error_counts.items()],
    )


def _load_api_metrics(
    conn: sqlite3.Connection, api_latency: dict[str, float]
) -> None:
    """Insert API latency averages via parameterised query."""
    now = datetime.datetime.now().isoformat()
    conn.executemany(
        "INSERT INTO api_metrics (dt, endpoint, avg_ms) VALUES (?, ?, ?)",
        [(now, ep, avg) for ep, avg in api_latency.items()],
    )


def _build_html_report(summary: Summary) -> str:
    """Render the summary as a standalone HTML report."""
    lines: list[str] = [
        "<html>",
        "<head><title>System Report</title></head>",
        "<body>",
        "<h1>Error Summary</h1>",
        "<ul>",
    ]
    for msg, cnt in summary["error_counts"].items():
        lines.append(f"<li><b>{msg}</b>: {cnt} occurrences</li>")
    lines += [
        "</ul>",
        "<h2>API Latency</h2>",
        "<table border='1'>",
        "<tr><th>Endpoint</th><th>Avg (ms)</th></tr>",
    ]
    for ep, avg in sorted(summary["api_latency"].items()):
        lines.append(f"<tr><td>{ep}</td><td>{round(avg, 1)}</td></tr>")
    lines += [
        "</table>",
        "<h2>Active Sessions</h2>",
        f"<p>{summary['active_sessions']} user(s) currently active</p>",
        "</body>",
        "</html>",
    ]
    return "\n".join(lines)


def load(summary: Summary) -> None:
    """Persist the summary to SQLite and write report.html."""
    conn = _init_db(DB_PATH)
    try:
        _load_errors(conn, summary["error_counts"])
        _load_api_metrics(conn, summary["api_latency"])
        conn.commit()
    finally:
        conn.close()

    report_html = _build_html_report(summary)
    with open("report.html", "w") as f:
        f.write(report_html)

    print(f"Report written to report.html  ({len(summary['events'])} events processed)")


# ---------------------------------------------------------------------------
# Pipeline entry point
# ---------------------------------------------------------------------------

def run_pipeline(log_path: str = LOG_FILE_PATH) -> Summary:
    """Execute the full Extract → Transform → Load pipeline.

    Args:
        log_path: Path to the server log file.

    Returns:
        The computed summary (useful for testing / inspection).
    """
    print(f"[pipeline] Extracting from {log_path} …")
    events = extract(log_path)
    print(f"[pipeline] {len(events)} events parsed")

    print("[pipeline] Transforming …")
    summary = transform(events)

    print("[pipeline] Loading …")
    load(summary)

    print(f"[pipeline] Done at {datetime.datetime.now()}")
    return summary


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _generate_sample_data(path: str) -> None:
    """Write a small sample log to *path* if it does not already exist."""
    sample = (
        "2024-01-01 12:00:00 INFO User 42 logged in\n"
        "2024-01-01 12:05:00 ERROR Database timeout\n"
        "2024-01-01 12:05:05 ERROR Database timeout\n"
        "2024-01-01 12:08:00 INFO API /users/profile took 250ms\n"
        "2024-01-01 12:09:00 WARN Memory usage at 87%\n"
        "2024-01-01 12:10:00 INFO User 42 logged out\n"
    )
    with open(path, "w") as f:
        f.write(sample)
    print(f"Sample data written to {path}")


if __name__ == "__main__":
    if not os.path.exists(LOG_FILE_PATH):
        _generate_sample_data(LOG_FILE_PATH)
    run_pipeline()
