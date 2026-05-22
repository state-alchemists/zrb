"""Refactored server-log pipeline — Extract, Transform, Load with parameterized SQL and regex parsing.

Reads a server log file, extracts error/user/API/WARN events,
aggregates them, persists to SQLite, and writes an HTML report.
All configuration comes from environment variables with sensible defaults.
"""

from __future__ import annotations

import datetime
import os
import re
import sqlite3
from collections import Counter
from typing import Any, Dict, List, Tuple

# ---------------------------------------------------------------------------
# Configuration —  all from environment variables, never hardcoded
# ---------------------------------------------------------------------------

DB_PATH: str = os.getenv("DB_PATH", "metrics.db")
LOG_FILE: str = os.getenv("LOG_FILE", "server.log")
DB_HOST: str = os.getenv("DB_HOST", "localhost")
DB_PORT: str = os.getenv("DB_PORT", "5432")
DB_USER: str = os.getenv("DB_USER", "admin")
DB_PASS: str = os.getenv("DB_PASS", "")  # deliberately no fallback value

# Regex patterns for each log-line type.
_RE_ERROR = re.compile(
    r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) ERROR (.+)$"
)
_RE_USER = re.compile(
    r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) INFO User (\d+) (.+)$"
)
_RE_API = re.compile(
    r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) INFO API (.+) took (\d+)ms$"
)
_RE_WARN = re.compile(
    r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) WARN (.+)$"
)

# ---------------------------------------------------------------------------
# Extract
# ---------------------------------------------------------------------------


def extract_logs(
    path: str,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, str]]:
    """Parse *path* and return (errors, api_calls, sessions).

    Each error is ``{"dt": str, "message": str}``.
    Each api_call is ``{"dt": str, "endpoint": str, "ms": int}``.
    Sessions are tracked live as ``{user_id: login_timestamp}``.
    """
    errors: List[Dict[str, Any]] = []
    api_calls: List[Dict[str, Any]] = []
    sessions: Dict[str, str] = {}

    if not os.path.exists(path):
        return errors, api_calls, sessions

    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            m = _RE_ERROR.match(line)
            if m:
                errors.append({"dt": m.group(1), "message": m.group(2)})
                continue

            m = _RE_USER.match(line)
            if m:
                dt, uid, action = m.group(1), m.group(2), m.group(3)
                if "logged in" in action:
                    sessions[uid] = dt
                elif "logged out" in action and uid in sessions:
                    del sessions[uid]
                continue

            m = _RE_API.match(line)
            if m:
                api_calls.append(
                    {"dt": m.group(1), "endpoint": m.group(2), "ms": int(m.group(3))}
                )
                continue

            m = _RE_WARN.match(line)
            # WARN lines are noted but not persisted in the current schema

    return errors, api_calls, sessions


# ---------------------------------------------------------------------------
# Transform
# ---------------------------------------------------------------------------


def transform_errors(errors: List[Dict[str, Any]]) -> Dict[str, int]:
    """Aggregate error messages into ``{message: count}``."""
    return dict(Counter(e["message"] for e in errors))


def transform_api_latency(api_calls: List[Dict[str, Any]]) -> Dict[str, float]:
    """Compute average latency in ms per API endpoint."""
    agg: Dict[str, List[int]] = {}
    for call in api_calls:
        agg.setdefault(call["endpoint"], []).append(call["ms"])
    return {ep: sum(times) / len(times) for ep, times in agg.items()}


# ---------------------------------------------------------------------------
# Load —  database
# ---------------------------------------------------------------------------


def _init_db(conn: sqlite3.Connection) -> None:
    """Create tables if they do not exist."""
    conn.execute(
        "CREATE TABLE IF NOT EXISTS errors (dt TEXT, message TEXT, count INTEGER)"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS api_metrics (dt TEXT, endpoint TEXT, avg_ms REAL)"
    )


def load_to_database(
    errors_by_msg: Dict[str, int],
    api_latency: Dict[str, float],
    db_path: str,
) -> None:
    """Persist transformed metrics into *db_path* using parameterized queries."""
    print(
        f"Connecting to {DB_HOST}:{DB_PORT} as {DB_USER}..."
    )
    conn = sqlite3.connect(db_path)
    try:
        _init_db(conn)
        now = datetime.datetime.now().isoformat()

        for msg, count in errors_by_msg.items():
            conn.execute(
                "INSERT INTO errors (dt, message, count) VALUES (?, ?, ?)",
                (now, msg, count),
            )

        for ep, avg in api_latency.items():
            conn.execute(
                "INSERT INTO api_metrics (dt, endpoint, avg_ms) VALUES (?, ?, ?)",
                (now, ep, avg),
            )

        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Load —  report
# ---------------------------------------------------------------------------


def _build_error_summary_html(errors_by_msg: Dict[str, int]) -> str:
    """Render the error-summary `<ul>` block."""
    parts = ["<h1>Error Summary</h1>\n<ul>"]
    for msg, count in errors_by_msg.items():
        parts.append(f"<li><b>{msg}</b>: {count} occurrences</li>")
    parts.append("</ul>\n")
    return "\n".join(parts)


def _build_api_latency_html(api_latency: Dict[str, float]) -> str:
    """Render the API-latency `<table>` block."""
    parts = [
        "<h2>API Latency</h2>\n<table border='1'>",
        "<tr><th>Endpoint</th><th>Avg (ms)</th></tr>",
    ]
    for ep, avg in api_latency.items():
        parts.append(f"<tr><td>{ep}</td><td>{round(avg, 1)}</td></tr>")
    parts.append("</table>\n")
    return "\n".join(parts)


def _build_sessions_html(active_count: int) -> str:
    """Render the active-sessions block."""
    return f"<h2>Active Sessions</h2>\n<p>{active_count} user(s) currently active</p>\n"


def generate_report(
    errors_by_msg: Dict[str, int],
    api_latency: Dict[str, float],
    active_session_count: int,
    output_path: str,
) -> None:
    """Write an HTML report to *output_path*."""
    sections = [
        "<html>\n<head><title>System Report</title></head>\n<body>",
        _build_error_summary_html(errors_by_msg),
        _build_api_latency_html(api_latency),
        _build_sessions_html(active_session_count),
        "</body>\n</html>",
    ]
    with open(output_path, "w") as f:
        f.write("\n".join(sections))


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def main() -> None:
    """Run the full pipeline: extract → transform → load → report."""
    errors, api_calls, sessions = extract_logs(LOG_FILE)
    errors_by_msg = transform_errors(errors)
    api_latency = transform_api_latency(api_calls)

    load_to_database(errors_by_msg, api_latency, DB_PATH)

    generate_report(errors_by_msg, api_latency, len(sessions), "report.html")

    print(f"Job finished at {datetime.datetime.now()}")


if __name__ == "__main__":
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, "w") as f:
            f.write("2024-01-01 12:00:00 INFO User 42 logged in\n")
            f.write("2024-01-01 12:05:00 ERROR Database timeout\n")
            f.write("2024-01-01 12:05:05 ERROR Database timeout\n")
            f.write("2024-01-01 12:08:00 INFO API /users/profile took 250ms\n")
            f.write("2024-01-01 12:09:00 WARN Memory usage at 87%\n")
            f.write("2024-01-01 12:10:00 INFO User 42 logged out\n")
    main()
