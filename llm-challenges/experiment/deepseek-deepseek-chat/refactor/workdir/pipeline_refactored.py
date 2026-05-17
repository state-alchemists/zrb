"""
pipeline_refactored.py — Extract → Transform → Load pipeline for server log analysis.

Reads a server log file, parses structured events (ERROR, WARN, user login/logout,
API call timing), stores aggregates in SQLite via parameterized queries, and
produces an HTML report with error summary, API latency table, and active session count.

Configuration is loaded from environment variables — no hardcoded credentials or paths.
"""

import datetime
import os
import re
import sqlite3
from collections import defaultdict
from typing import Any, Dict, List, Tuple

# ---------------------------------------------------------------------------
# Configuration — all from environment variables with sensible defaults
# ---------------------------------------------------------------------------

DB_PATH: str = os.environ.get("PIPELINE_DB_PATH", "metrics.db")
LOG_FILE: str = os.environ.get("PIPELINE_LOG_FILE", "server.log")


# ---------------------------------------------------------------------------
# Extract — read raw log and return structured event records
# ---------------------------------------------------------------------------

# Log-line regex with named groups. Supports both space-separated and
# ISO-8601-like timestamps (YYYY-MM-DD HH:MM:SS).
_LOG_LINE_RE = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\s+"
    r"(?P<level>ERROR|INFO|WARN)\s+"
    r"(?P<message>.+)$"
)

# Patterns for INFO-level sub-types (dispatched after the level check).
_RE_USER_ACTION = re.compile(
    r"^User\s+(?P<user_id>\S+)\s+(?P<action>.+)$"
)
_RE_API_CALL = re.compile(
    r"^API\s+(?P<endpoint>\S+)\s+took\s+(?P<duration_ms>\d+)ms"
)


def _parse_log_line(line: str) -> Dict[str, Any] | None:
    """Parse a single log line into a structured dict, or None if unparseable.

    The returned dict always contains keys ``timestamp``, ``level``, and
    ``raw_message``.  Additional keys depend on the log level:

    - ``ERROR``, ``WARN`` → ``message``
    - ``INFO`` with a User action → ``user_id``, ``action``, ``session``
    - ``INFO`` with an API call → ``endpoint``, ``duration_ms``

    The ``session`` field is ``"login"`` or ``"logout"`` for User lines.
    """
    m = _LOG_LINE_RE.match(line.strip())
    if not m:
        return None

    record: Dict[str, Any] = {
        "timestamp": m.group("timestamp"),
        "level": m.group("level"),
        "raw_message": m.group("message"),
    }

    level = record["level"]
    body = m.group("message")

    if level == "ERROR":
        record["message"] = body
    elif level == "WARN":
        record["message"] = body
    elif level == "INFO":
        # Try user action first
        user_m = _RE_USER_ACTION.match(body)
        if user_m:
            record["user_id"] = user_m.group("user_id")
            record["action"] = user_m.group("action")
            record["session"] = (
                "login" if "logged in" in user_m.group("action") else "logout"
            )
            return record
        # Then API call
        api_m = _RE_API_CALL.match(body)
        if api_m:
            record["endpoint"] = api_m.group("endpoint")
            record["duration_ms"] = int(api_m.group("duration_ms"))
            return record

    return record


def extract_events(log_path: str) -> List[Dict[str, Any]]:
    """Read ``log_path`` and return a list of structured event dicts.

    Lines that cannot be parsed are silently skipped.
    """
    events: List[Dict[str, Any]] = []
    if not os.path.exists(log_path):
        return events

    with open(log_path, "r") as f:
        for line in f:
            rec = _parse_log_line(line)
            if rec is not None:
                events.append(rec)
    return events


# ---------------------------------------------------------------------------
# Transform — derive aggregations from raw events
# ---------------------------------------------------------------------------


def _build_error_counts(events: List[Dict[str, Any]]) -> Dict[str, int]:
    """Return {error_message: count} from ERROR-level events."""
    counts: Dict[str, int] = defaultdict(int)
    for ev in events:
        if ev["level"] == "ERROR":
            counts[ev["message"]] += 1
    return dict(counts)


def _build_api_latency(
    events: List[Dict[str, Any]],
) -> Dict[str, List[int]]:
    """Return {endpoint: [duration_ms, ...]} from API-call events."""
    by_endpoint: Dict[str, List[int]] = defaultdict(list)
    for ev in events:
        if ev.get("endpoint"):
            by_endpoint[ev["endpoint"]].append(ev["duration_ms"])
    return dict(by_endpoint)


def _build_session_tracker(
    events: List[Dict[str, Any]],
) -> Dict[str, str]:
    """Replay login/logout events; return {user_id: timestamp} for active sessions."""
    sessions: Dict[str, str] = {}
    for ev in events:
        if ev.get("session") == "login":
            sessions[ev["user_id"]] = ev["timestamp"]
        elif ev.get("session") == "logout":
            sessions.pop(ev["user_id"], None)
    return sessions


def transform_events(
    events: List[Dict[str, Any]],
) -> Tuple[Dict[str, int], Dict[str, List[int]], Dict[str, str]]:
    """Derive error counts, API latency map, and active sessions from events.

    Returns (error_counts, api_latency_by_endpoint, active_sessions).
    """
    return (
        _build_error_counts(events),
        _build_api_latency(events),
        _build_session_tracker(events),
    )


# ---------------------------------------------------------------------------
# Load — write aggregations to SQLite and produce the HTML report
# ---------------------------------------------------------------------------


def _get_db_connection(db_path: str) -> sqlite3.Connection:
    """Open a connection to *db_path* and ensure the target tables exist."""
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


def _store_error_summary(
    conn: sqlite3.Connection, counts: Dict[str, int]
) -> None:
    """Insert error-count rows with parameterized queries (no injection)."""
    now = datetime.datetime.now().isoformat()
    conn.executemany(
        "INSERT INTO errors (dt, message, count) VALUES (?, ?, ?)",
        [(now, msg, cnt) for msg, cnt in counts.items()],
    )


def _store_api_latency(
    conn: sqlite3.Connection, by_endpoint: Dict[str, List[int]]
) -> None:
    """Insert per-endpoint average latency with parameterized queries."""
    now = datetime.datetime.now().isoformat()
    rows = [
        (now, ep, sum(times) / len(times)) for ep, times in by_endpoint.items()
    ]
    conn.executemany(
        "INSERT INTO api_metrics (dt, endpoint, avg_ms) VALUES (?, ?, ?)",
        rows,
    )


def _write_html_report(
    counts: Dict[str, int],
    by_endpoint: Dict[str, List[int]],
    sessions: Dict[str, str],
) -> None:
    """Write ``report.html`` with error summary, API latency table, and active session count."""
    lines: List[str] = [
        "<html>",
        "<head><title>System Report</title></head>",
        "<body>",
        "<h1>Error Summary</h1>",
        "<ul>",
    ]
    for msg, cnt in counts.items():
        lines.append(
            f"<li><b>{msg}</b>: {cnt} occurrences</li>"
        )
    lines.append("</ul>")

    lines.append("<h2>API Latency</h2>")
    lines.append("<table border='1'>")
    lines.append("<tr><th>Endpoint</th><th>Avg (ms)</th></tr>")
    for ep, times in by_endpoint.items():
        avg = sum(times) / len(times)
        lines.append(
            f"<tr><td>{ep}</td><td>{round(avg, 1)}</td></tr>"
        )
    lines.append("</table>")

    lines.append("<h2>Active Sessions</h2>")
    lines.append(f"<p>{len(sessions)} user(s) currently active</p>")
    lines.append("</body>")
    lines.append("</html>")

    with open("report.html", "w") as f:
        f.write("\n".join(lines))


def load_and_report(
    counts: Dict[str, int],
    by_endpoint: Dict[str, List[int]],
    sessions: Dict[str, str],
    db_path: str,
) -> None:
    """Write aggregations to SQLite (parameterized) and produce ``report.html``."""
    conn = _get_db_connection(db_path)
    try:
        _store_error_summary(conn, counts)
        _store_api_latency(conn, by_endpoint)
        conn.commit()
    finally:
        conn.close()

    _write_html_report(counts, by_endpoint, sessions)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Run the full Extract → Transform → Load pipeline."""
    events = extract_events(LOG_FILE)
    if not events:
        print("No events found — check PIPELINE_LOG_FILE")
        return

    counts, by_endpoint, sessions = transform_events(events)
    load_and_report(counts, by_endpoint, sessions, DB_PATH)

    print(f"Report written to report.html — {len(sessions)} active session(s)")


if __name__ == "__main__":
    # Seed a sample log file if one doesn't exist (keeps the original behaviour).
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, "w") as f:
            f.write("2024-01-01 12:00:00 INFO User 42 logged in\n")
            f.write("2024-01-01 12:05:00 ERROR Database timeout\n")
            f.write("2024-01-01 12:05:05 ERROR Database timeout\n")
            f.write("2024-01-01 12:08:00 INFO API /users/profile took 250ms\n")
            f.write("2024-01-01 12:09:00 WARN Memory usage at 87%\n")
            f.write("2024-01-01 12:10:00 INFO User 42 logged out\n")
    main()
