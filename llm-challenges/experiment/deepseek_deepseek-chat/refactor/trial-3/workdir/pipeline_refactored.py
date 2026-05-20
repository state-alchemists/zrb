"""Refactored server-log pipeline: Extract → Transform → Load.

Reads a server log file, parses structured events via regex,
computes error summaries, API latency stats, and active session
counts, then persists results to SQLite and produces report.html.
"""

from __future__ import annotations

import datetime
import os
import re
import sqlite3
from typing import Any, Dict, List, Tuple


# ---------------------------------------------------------------------------
# Configuration — all via environment variables with sensible defaults
# ---------------------------------------------------------------------------

_LOG_FILE = os.getenv("LOG_FILE", "server.log")
_DB_PATH = os.getenv("DB_PATH", "metrics.db")
_DB_HOST = os.getenv("DB_HOST", "localhost")
_DB_PORT = os.getenv("DB_PORT", "5432")
_DB_USER = os.getenv("DB_USER", "admin")
_DB_PASS = os.getenv("DB_PASS", "changeme")

# Regex for a single log line: <timestamp> <LEVEL> <message...>
_LINE_RE = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) "
    r"(?P<level>INFO|ERROR|WARN) "
    r"(?P<message>.+)$"
)


# ---------------------------------------------------------------------------
# Extract
# ---------------------------------------------------------------------------


def extract_logs(log_path: str) -> List[Dict[str, str]]:
    """Parse *log_path* line-by-line into a list of structured records.

    Each record contains keys ``timestamp``, ``level``, and ``message``.
    Lines that don't match the expected format are silently skipped.
    """
    records: List[Dict[str, str]] = []
    if not os.path.exists(log_path):
        return records

    with open(log_path, "r") as f:
        for line in f:
            line = line.strip()
            m = _LINE_RE.match(line)
            if m is None:
                continue
            records.append(m.groupdict())

    return records


# ---------------------------------------------------------------------------
# Transform
# ---------------------------------------------------------------------------


def _parse_user_action(
    message: str,
) -> Tuple[str, str] | None:
    """Extract ``(user_id, action)`` from a ``User <id> <action>`` message, or ``None``."""
    m = re.match(r"User (\S+) (.+)", message)
    if m is None:
        return None
    return m.group(1), m.group(2)


def _parse_api_call(message: str) -> Tuple[str, int] | None:
    """Extract ``(endpoint, duration_ms)`` from an ``API <ep> took <n>ms`` message, or ``None``."""
    m = re.match(r"API (\S+) took (\d+)ms", message)
    if m is None:
        return None
    return m.group(1), int(m.group(2))


def _aggregate_errors(
    records: List[Dict[str, str]],
) -> Dict[str, int]:
    """Sum occurrences of each distinct ERROR message."""
    err_counts: Dict[str, int] = {}
    for rec in records:
        if rec["level"] == "ERROR":
            msg = rec["message"]
            err_counts[msg] = err_counts.get(msg, 0) + 1
    return err_counts


def _aggregate_api_latency(
    records: List[Dict[str, str]],
) -> Dict[str, List[int]]:
    """Group API call durations by endpoint."""
    stats: Dict[str, List[int]] = {}
    for rec in records:
        if rec["level"] != "INFO":
            continue
        parsed = _parse_api_call(rec["message"])
        if parsed is None:
            continue
        ep, dur = parsed
        stats.setdefault(ep, []).append(dur)
    return stats


def _compute_active_sessions(
    records: List[Dict[str, str]],
) -> int:
    """Track login/logout events and return the number of still-active sessions."""
    sessions: Dict[str, str] = {}
    for rec in records:
        if rec["level"] != "INFO":
            continue
        parsed = _parse_user_action(rec["message"])
        if parsed is None:
            continue
        uid, action = parsed
        if "logged in" in action:
            sessions[uid] = rec["timestamp"]
        elif "logged out" in action and uid in sessions:
            del sessions[uid]
    return len(sessions)


def transform_logs(
    records: List[Dict[str, str]],
) -> Tuple[Dict[str, int], Dict[str, float], int]:
    """Convert raw log records into the three summary artifacts.

    Returns:
        (error_summary, api_latency_avgs, active_session_count)
        where *error_summary* maps error message → count,
        and *api_latency_avgs* maps endpoint → average duration (ms).
    """
    err_counts = _aggregate_errors(records)
    api_raw = _aggregate_api_latency(records)
    api_avgs: Dict[str, float] = {
        ep: sum(times) / len(times) for ep, times in api_raw.items()
    }
    active = _compute_active_sessions(records)
    return err_counts, api_avgs, active


# ---------------------------------------------------------------------------
# Load
# ---------------------------------------------------------------------------


def _init_db(db_path: str) -> sqlite3.Connection:
    """Open *db_path* and ensure the required tables exist."""
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute(
        "CREATE TABLE IF NOT EXISTS errors "
        "(dt TEXT, message TEXT, count INTEGER)"
    )
    c.execute(
        "CREATE TABLE IF NOT EXISTS api_metrics "
        "(dt TEXT, endpoint TEXT, avg_ms REAL)"
    )
    conn.commit()
    return conn


def _write_error_summary(
    conn: sqlite3.Connection,
    err_counts: Dict[str, int],
) -> None:
    """Persist error counts to the ``errors`` table (parameterized query)."""
    now = str(datetime.datetime.now())
    c = conn.cursor()
    for msg, count in err_counts.items():
        c.execute(
            "INSERT INTO errors (dt, message, count) VALUES (?, ?, ?)",
            (now, msg, count),
        )
    conn.commit()


def _write_api_metrics(
    conn: sqlite3.Connection,
    api_avgs: Dict[str, float],
) -> None:
    """Persist average API latencies to the ``api_metrics`` table (parameterized query)."""
    now = str(datetime.datetime.now())
    c = conn.cursor()
    for ep, avg in api_avgs.items():
        c.execute(
            "INSERT INTO api_metrics (dt, endpoint, avg_ms) VALUES (?, ?, ?)",
            (now, ep, avg),
        )
    conn.commit()


def _build_report_html(
    err_counts: Dict[str, int],
    api_avgs: Dict[str, float],
    active_sessions: int,
) -> str:
    """Assemble a self-contained HTML report document."""
    parts: List[str] = [
        "<html>",
        "<head><title>System Report</title></head>",
        "<body>",
        "<h1>Error Summary</h1>",
        "<ul>",
    ]
    for msg, count in err_counts.items():
        parts.append(f"<li><b>{msg}</b>: {count} occurrences</li>")
    parts.append("</ul>")

    parts.append("<h2>API Latency</h2>")
    parts.append("<table border='1'>")
    parts.append("<tr><th>Endpoint</th><th>Avg (ms)</th></tr>")
    for ep, avg in sorted(api_avgs.items()):
        parts.append(f"<tr><td>{ep}</td><td>{avg:.1f}</td></tr>")
    parts.append("</table>")

    parts.append("<h2>Active Sessions</h2>")
    parts.append(f"<p>{active_sessions} user(s) currently active</p>")
    parts.append("</body>")
    parts.append("</html>")
    return "\n".join(parts)


def load_report(
    err_counts: Dict[str, int],
    api_avgs: Dict[str, float],
    active_sessions: int,
    db_path: str,
    html_path: str,
) -> None:
    """Persist results to SQLite and write the HTML report to *html_path*.

    The database tables (``errors``, ``api_metrics``) are created if they
    do not already exist. All SQL uses parameterized queries.
    """
    conn = _init_db(db_path)
    _write_error_summary(conn, err_counts)
    _write_api_metrics(conn, api_avgs)
    conn.close()

    html = _build_report_html(err_counts, api_avgs, active_sessions)
    with open(html_path, "w") as f:
        f.write(html)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Run the full Extract → Transform → Load pipeline.

    Environment variables (``LOG_FILE``, ``DB_PATH``, etc.) control
    input and output locations.
    """
    print(f"Connecting to {_DB_HOST}:{_DB_PORT} as {_DB_USER}...")

    records = extract_logs(_LOG_FILE)
    err_counts, api_avgs, active_sessions = transform_logs(records)
    load_report(err_counts, api_avgs, active_sessions, _DB_PATH, "report.html")

    print(f"Job finished at {datetime.datetime.now()}")


if __name__ == "__main__":
    if not os.path.exists(_LOG_FILE):
        with open(_LOG_FILE, "w") as f:
            f.write("2024-01-01 12:00:00 INFO User 42 logged in\n")
            f.write("2024-01-01 12:05:00 ERROR Database timeout\n")
            f.write("2024-01-01 12:05:05 ERROR Database timeout\n")
            f.write("2024-01-01 12:08:00 INFO API /users/profile took 250ms\n")
            f.write("2024-01-01 12:09:00 WARN Memory usage at 87%\n")
            f.write("2024-01-01 12:10:00 INFO User 42 logged out\n")
    main()
