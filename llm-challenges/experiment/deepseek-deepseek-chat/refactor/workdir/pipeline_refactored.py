"""
Refactored log-processing pipeline.

Extract -> Transform -> Load pattern with parameterized SQL, regex-based
parsing, environment-variable config, and full type hints.
"""

from __future__ import annotations

import datetime
import os
import re
import sqlite3
from collections import defaultdict
from typing import Dict, List, Tuple


# ---------------------------------------------------------------------------
# Configuration via environment variables
# ---------------------------------------------------------------------------

DB_PATH: str = os.environ.get("PIPELINE_DB_PATH", "metrics.db")
LOG_FILE: str = os.environ.get("PIPELINE_LOG_FILE", "server.log")
# Legacy DB fields kept for backwards compat with the original print statement
DB_HOST: str = os.environ.get("PIPELINE_DB_HOST", "localhost")
DB_PORT: int = int(os.environ.get("PIPELINE_DB_PORT", "5432"))
DB_USER: str = os.environ.get("PIPELINE_DB_USER", "admin")
DB_PASS: str = os.environ.get("PIPELINE_DB_PASS", "")

# Sensible defaults if none are set – only for local development
if not DB_PASS and DB_USER == "admin":
    DB_PASS = os.environ.get("PIPELINE_DB_PASS", "")


# ---------------------------------------------------------------------------
# Data structures (typed)
# ---------------------------------------------------------------------------

LogEntry = Dict[str, str | int]
ApiCall = Dict[str, str | int]
SessionStore = Dict[str, str]  # user-id -> login timestamp


# ---------------------------------------------------------------------------
# REGEX PATTERNS
# ---------------------------------------------------------------------------

# Common log-line skeleton:  <timestamp> <level> <payload...>
LINE_RE = re.compile(
    r"^(?P<dt>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s+"
    r"(?P<level>ERROR|INFO|WARN)\s+"
    r"(?P<payload>.*)$"
)

ERROR_RE = re.compile(r".*", re.DOTALL)  # whole rest of line is the message

USER_RE = re.compile(
    r"User\s+(?P<uid>\S+)\s+(?P<action>logged in|logged out|.*)"
)

API_RE = re.compile(
    r"API\s+(?P<endpoint>\S+).*?took\s+(?P<ms>\d+)\s*ms"
)


# ---------------------------------------------------------------------------
# EXTRACT
# ---------------------------------------------------------------------------

def read_log_lines(path: str) -> List[str]:
    """Return all non-empty lines from *path*, or an empty list."""
    if not os.path.exists(path):
        print(f"WARN: log file '{path}' not found – continuing with empty data")
        return []
    with open(path, "r") as f:
        return [line.rstrip("\n") for line in f if line.strip()]


# ---------------------------------------------------------------------------
# TRANSFORM
# ---------------------------------------------------------------------------

def parse_line(line: str) -> LogEntry | None:
    """
    Parse a single log line into a structured dict.

    Returns ``None`` for unrecognized lines.  Recognized types:
      - ``ERR``   – ERROR messages
      - ``USR``   – INFO lines mentioning a User (login/logout)
      - ``API``   – INFO lines with API timing
      - ``WARN``  – WARN messages
    """
    m = LINE_RE.match(line)
    if not m:
        return None

    dt = m.group("dt")
    level = m.group("level")
    payload = m.group("payload")

    if level == "ERROR":
        return {"dt": dt, "type": "ERR", "message": payload.strip()}

    if level == "WARN":
        return {"dt": dt, "type": "WARN", "message": payload.strip()}

    # level == "INFO"
    user_m = USER_RE.search(payload)
    if user_m:
        return {
            "dt": dt,
            "type": "USR",
            "user_id": user_m.group("uid"),
            "action": user_m.group("action").strip(),
        }

    api_m = API_RE.search(payload)
    if api_m:
        return {
            "dt": dt,
            "type": "API",
            "endpoint": api_m.group("endpoint"),
            "latency_ms": int(api_m.group("ms")),
        }

    return None


def _track_session(entry: LogEntry, sessions: SessionStore) -> None:
    """Update *sessions* dict based on a USR entry (mutates in place)."""
    assert entry["type"] == "USR"
    uid = entry["user_id"]  # type: ignore[assignment]
    action = entry["action"]  # type: ignore[assignment]
    dt = entry["dt"]  # type: ignore[assignment]

    if action == "logged in":
        sessions[uid] = dt  # type: ignore[index]
    elif action == "logged out" and uid in sessions:
        del sessions[uid]


def _aggregate_errors(entries: List[LogEntry]) -> Dict[str, int]:
    """Return {message: count} for every ERR entry."""
    counts: Dict[str, int] = {}
    for e in entries:
        if e.get("type") == "ERR":
            msg = e["message"]  # type: ignore[assignment]
            counts[msg] = counts.get(msg, 0) + 1
    return counts


def _aggregate_api_latency(entries: List[LogEntry]) -> Dict[str, List[int]]:
    """Return {endpoint: [list of latency_ms]} for every API entry."""
    stats: Dict[str, List[int]] = defaultdict(list)
    for e in entries:
        if e.get("type") == "API":
            stats[e["endpoint"]].append(e["latency_ms"])  # type: ignore[arg-type]
    return dict(stats)


def transform(lines: List[str]) -> Tuple[LogEntry, Dict[str, int], Dict[str, List[int]], SessionStore]:
    """
    Apply all transformation logic (parsing, session tracking, aggregation).

    Returns ``(all_entries, error_counts, api_latency_map, sessions)``.
    """
    sessions: SessionStore = {}
    entries: List[LogEntry] = []

    for line in lines:
        parsed = parse_line(line)
        if parsed is None:
            continue
        entries.append(parsed)
        if parsed.get("type") == "USR":
            _track_session(parsed, sessions)

    error_counts = _aggregate_errors(entries)
    api_latency = _aggregate_api_latency(entries)

    return entries, error_counts, api_latency, sessions


# ---------------------------------------------------------------------------
# LOAD – database
# ---------------------------------------------------------------------------

def _init_db(conn: sqlite3.Connection) -> None:
    """Create tables if they don't exist."""
    conn.execute(
        "CREATE TABLE IF NOT EXISTS errors "
        "(dt TEXT, message TEXT, count INTEGER)"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS api_metrics "
        "(dt TEXT, endpoint TEXT, avg_ms REAL)"
    )
    conn.commit()


def _write_errors(conn: sqlite3.Connection, errors: Dict[str, int]) -> None:
    """Insert aggregated error rows using parameterized query."""
    now = datetime.datetime.now().isoformat()
    conn.executemany(
        "INSERT INTO errors (dt, message, count) VALUES (?, ?, ?)",
        [(now, msg, cnt) for msg, cnt in errors.items()],
    )
    conn.commit()


def _write_api_metrics(conn: sqlite3.Connection, api_latency: Dict[str, List[int]]) -> None:
    """Insert average API latency rows using parameterized query."""
    now = datetime.datetime.now().isoformat()
    rows = [
        (now, ep, sum(times) / len(times))
        for ep, times in api_latency.items()
        if times
    ]
    conn.executemany(
        "INSERT INTO api_metrics (dt, endpoint, avg_ms) VALUES (?, ?, ?)",
        rows,
    )
    conn.commit()


def load_to_db(errors: Dict[str, int], api_latency: Dict[str, List[int]]) -> None:
    """
    Write error summary and API latency metrics into the SQLite database.

    Reads ``DB_PATH`` from module-level config.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        _init_db(conn)
        _write_errors(conn, errors)
        _write_api_metrics(conn, api_latency)
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# LOAD – HTML report
# ---------------------------------------------------------------------------

def build_html_report(
    errors: Dict[str, int],
    api_latency: Dict[str, List[int]],
    active_sessions: int,
) -> str:
    """
    Generate a standalone HTML report string.

    Sections:
      1. Error summary (unordered list)
      2. API latency table (endpoint, avg ms)
      3. Active session count
    """
    parts: List[str] = [
        "<html>\n<head><title>System Report</title></head>\n<body>",
        "<h1>Error Summary</h1>\n<ul>",
    ]

    for err_msg, count in errors.items():
        parts.append(f"<li><b>{_escape_html(err_msg)}</b>: {count} occurrences</li>")
    parts.append("</ul>")

    parts.append("<h2>API Latency</h2>\n<table border='1'>")
    parts.append("<tr><th>Endpoint</th><th>Avg (ms)</th></tr>")
    for ep, times in api_latency.items():
        if not times:
            continue
        avg = sum(times) / len(times)
        parts.append(f"<tr><td>{_escape_html(ep)}</td><td>{avg:.1f}</td></tr>")
    parts.append("</table>")

    parts.append("<h2>Active Sessions</h2>")
    parts.append(f"<p>{active_sessions} user(s) currently active</p>")
    parts.append("</body>\n</html>")

    return "\n".join(parts)


def _escape_html(text: str) -> str:
    """Minimal HTML-entity escaping to prevent XSS in report output."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def write_html_report(path: str, html: str) -> None:
    """Write *html* to *path*."""
    with open(path, "w") as f:
        f.write(html)


# ---------------------------------------------------------------------------
# PIPELINE ENTRY POINT
# ---------------------------------------------------------------------------

def run_pipeline() -> None:
    """Execute the full Extract-Transform-Load pipeline."""
    print(
        f"Connecting to {DB_HOST}:{DB_PORT} as {DB_USER}..."
        if DB_USER
        else "Running in local-only mode (no remote DB connection)."
    )

    # Extract
    lines = read_log_lines(LOG_FILE)

    # Transform
    _, errors, api_latency, sessions = transform(lines)

    # Load – database
    load_to_db(errors, api_latency)

    # Load – HTML report
    html = build_html_report(errors, api_latency, len(sessions))
    write_html_report("report.html", html)

    print(f"Pipeline finished at {datetime.datetime.now()}")


# ---------------------------------------------------------------------------
# MAIN (test-data generator)
# ---------------------------------------------------------------------------

def _ensure_sample_log(path: str) -> None:
    """Write a sample log file if *path* doesn't already exist."""
    if os.path.exists(path):
        return
    lines = [
        "2024-01-01 12:00:00 INFO User 42 logged in",
        "2024-01-01 12:05:00 ERROR Database timeout",
        "2024-01-01 12:05:05 ERROR Database timeout",
        "2024-01-01 12:08:00 INFO API /users/profile took 250ms",
        "2024-01-01 12:09:00 WARN Memory usage at 87%",
        "2024-01-01 12:10:00 INFO User 42 logged out",
    ]
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    _ensure_sample_log(LOG_FILE)
    run_pipeline()
