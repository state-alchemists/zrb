"""Server log processing pipeline — Extract, Transform, Load.

Reads a server log file, parses entries with regex, aggregates error counts,
API latency stats, and active session tracking, then persists results to
SQLite and writes an HTML report.

Environment variables:
    PIPELINE_LOG_FILE  — path to the server log (default: server.log)
    PIPELINE_DB_PATH   — path to the SQLite database (default: metrics.db)
"""

import datetime
import os
import re
import sqlite3
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

LOG_FILE: str = os.environ.get("PIPELINE_LOG_FILE", "server.log")
DB_PATH: str = os.environ.get("PIPELINE_DB_PATH", "metrics.db")

# ---------------------------------------------------------------------------
# Domain types
# ---------------------------------------------------------------------------

LogKind = str  # "ERROR" | "WARN" | "USER" | "API"


@dataclass
class LogEntry:
    """A single parsed log line."""

    timestamp: str
    kind: LogKind
    message: str = ""
    user_id: str = ""
    action: str = ""
    endpoint: str = ""
    duration_ms: int = 0


# ---------------------------------------------------------------------------
# Extract — log line parsing via regex
# ---------------------------------------------------------------------------

# Regex patterns for each log line kind.
# Common prefix: "<timestamp> <LEVEL> " — captured by the outer dispatcher.

_RE_TIMESTAMP = r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}"

# ERROR  <message>
_RE_ERROR = re.compile(
    rf"^({_RE_TIMESTAMP})\s+ERROR\s+(.+)$"
)

# WARN  <message>
_RE_WARN = re.compile(
    rf"^({_RE_TIMESTAMP})\s+WARN\s+(.+)$"
)

# INFO  User <id> <action logged in / logged out>
_RE_USER = re.compile(
    rf"^({_RE_TIMESTAMP})\s+INFO\s+User\s+(\S+)\s+(logged in|logged out)"
)

# INFO  API <endpoint> took <ms>ms
_RE_API = re.compile(
    rf"^({_RE_TIMESTAMP})\s+INFO\s+API\s+(\S+)\s+took\s+(\d+)ms"
)


def parse_log_line(line: str) -> Optional[LogEntry]:
    """Parse a single log line into a ``LogEntry``, or ``None`` if
    the line does not match any known pattern."""
    line = line.strip()
    if not line:
        return None

    # Try known patterns — order matters: USER and API must be checked
    # before generic ERROR / WARN because they share the INFO level.

    m = _RE_API.match(line)
    if m:
        return LogEntry(
            timestamp=m.group(1),
            kind="API",
            endpoint=m.group(2),
            duration_ms=int(m.group(3)),
        )

    m = _RE_USER.match(line)
    if m:
        return LogEntry(
            timestamp=m.group(1),
            kind="USER",
            user_id=m.group(2),
            action=m.group(3),
        )

    m = _RE_ERROR.match(line)
    if m:
        return LogEntry(
            timestamp=m.group(1),
            kind="ERROR",
            message=m.group(2),
        )

    m = _RE_WARN.match(line)
    if m:
        return LogEntry(
            timestamp=m.group(1),
            kind="WARN",
            message=m.group(2),
        )

    return None


def extract_logs(log_path: str) -> List[LogEntry]:
    """Read *log_path* and return a list of successfully parsed entries."""
    entries: List[LogEntry] = []
    if not os.path.exists(log_path):
        return entries
    with open(log_path, "r") as f:
        for line in f:
            entry = parse_log_line(line)
            if entry is not None:
                entries.append(entry)
    return entries


# ---------------------------------------------------------------------------
# Transform — aggregate parsed entries into summaries
# ---------------------------------------------------------------------------


def aggregate_errors(entries: List[LogEntry]) -> Dict[str, int]:
    """Count occurrences of each unique error message.

    Only entries with ``kind == "ERROR"`` are considered.
    Returns ``{message: count}`` sorted by count descending.
    """
    counts: Dict[str, int] = {}
    for e in entries:
        if e.kind == "ERROR":
            counts[e.message] = counts.get(e.message, 0) + 1
    # Stable sort: highest count first, then alphabetical for ties.
    return dict(
        sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    )


def aggregate_api_calls(entries: List[LogEntry]) -> Dict[str, List[int]]:
    """Group API durations by endpoint.

    Only entries with ``kind == "API"`` are considered.
    Returns ``{endpoint: [duration_ms, ...]}``.
    """
    stats: Dict[str, List[int]] = {}
    for e in entries:
        if e.kind == "API":
            stats.setdefault(e.endpoint, []).append(e.duration_ms)
    return stats


def build_active_sessions(entries: List[LogEntry]) -> Dict[str, str]:
    """Track user session state across ``USER`` entries.

    Returns a dict of ``{user_id: login_timestamp}`` for currently
    active (logged-in) sessions.
    """
    sessions: Dict[str, str] = {}
    for e in entries:
        if e.kind != "USER":
            continue
        if e.action == "logged in":
            sessions[e.user_id] = e.timestamp
        elif e.action == "logged out":
            sessions.pop(e.user_id, None)
    return sessions


# ---------------------------------------------------------------------------
# Load — persist to database and generate HTML report
# ---------------------------------------------------------------------------


def _init_db(conn: sqlite3.Connection) -> None:
    """Create tables if they do not exist."""
    conn.execute(
        "CREATE TABLE IF NOT EXISTS errors "
        "(dt TEXT, message TEXT, count INTEGER)"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS api_metrics "
        "(dt TEXT, endpoint TEXT, avg_ms REAL)"
    )
    conn.commit()


def save_to_db(
    db_path: str,
    error_summary: Dict[str, int],
    api_stats: Dict[str, List[int]],
) -> None:
    """Persist aggregated results into a SQLite database.

    Uses parameterized queries to prevent SQL injection.
    """
    conn = sqlite3.connect(db_path)
    try:
        _init_db(conn)
        now = datetime.datetime.now().isoformat()

        # Parameterized INSERT — ``?`` placeholders, never string formatting.
        conn.executemany(
            "INSERT INTO errors (dt, message, count) VALUES (?, ?, ?)",
            [(now, msg, cnt) for msg, cnt in error_summary.items()],
        )

        api_rows: List[Tuple[str, str, float]] = []
        for ep, times in api_stats.items():
            avg = sum(times) / len(times)
            api_rows.append((now, ep, round(avg, 1)))
        conn.executemany(
            "INSERT INTO api_metrics (dt, endpoint, avg_ms) VALUES (?, ?, ?)",
            api_rows,
        )

        conn.commit()
    finally:
        conn.close()


def generate_report(
    error_summary: Dict[str, int],
    api_stats: Dict[str, List[int]],
    active_session_count: int,
) -> str:
    """Return an HTML string summarising errors, API latency and sessions."""
    lines: List[str] = [
        "<html>",
        "<head><title>System Report</title></head>",
        "<body>",
    ]

    # Error summary
    lines.append("<h1>Error Summary</h1>\n<ul>")
    for msg, count in error_summary.items():
        lines.append(
            f"<li><b>{_html_escape(msg)}</b>: "
            f"{count} occurrence{'s' if count != 1 else ''}</li>"
        )
    lines.append("</ul>")

    # API latency table
    lines.append("<h2>API Latency</h2>\n<table border='1'>")
    lines.append("<tr><th>Endpoint</th><th>Avg (ms)</th></tr>")
    for ep, times in api_stats.items():
        avg = sum(times) / len(times)
        lines.append(
            f"<tr><td>{_html_escape(ep)}</td>"
            f"<td>{round(avg, 1)}</td></tr>"
        )
    lines.append("</table>")

    # Active sessions
    lines.append("<h2>Active Sessions</h2>")
    lines.append(
        f"<p>{active_session_count} user(s) currently active</p>"
    )
    lines.append("</body>\n</html>")

    return "\n".join(lines)


def _html_escape(text: str) -> str:
    """Minimal HTML-entity escaping for safe embedding in HTML."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


# ---------------------------------------------------------------------------
# Pipeline orchestration
# ---------------------------------------------------------------------------


def run_pipeline(log_path: str, db_path: str, output_path: str = "report.html") -> str:
    """Execute the full extract → transform → load pipeline.

    Args:
        log_path: Path to the server log file.
        db_path: Path to the SQLite database file.
        output_path: Where to write the HTML report.

    Returns:
        The HTML report as a string (also written to *output_path*).
    """
    # Extract
    entries = extract_logs(log_path)
    if not entries:
        print(f"WARNING: no entries extracted from {log_path} — report will be empty.")

    # Transform
    error_summary = aggregate_errors(entries)
    api_stats = aggregate_api_calls(entries)
    sessions = build_active_sessions(entries)

    # Load — database
    save_to_db(db_path, error_summary, api_stats)

    # Load — report
    report_html = generate_report(
        error_summary=error_summary,
        api_stats=api_stats,
        active_session_count=len(sessions),
    )
    with open(output_path, "w") as f:
        f.write(report_html)

    print(
        f"Pipeline finished at {datetime.datetime.now().isoformat()} — "
        f"{len(error_summary)} error types, "
        f"{len(api_stats)} endpoints, "
        f"{len(sessions)} active session(s)"
    )
    return report_html


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Scaffold a sample log file if none exists.
    if not os.path.exists(LOG_FILE):
        sample = (
            "2024-01-01 12:00:00 INFO User 42 logged in\n"
            "2024-01-01 12:05:00 ERROR Database timeout\n"
            "2024-01-01 12:05:05 ERROR Database timeout\n"
            "2024-01-01 12:08:00 INFO API /users/profile took 250ms\n"
            "2024-01-01 12:09:00 WARN Memory usage at 87%\n"
            "2024-01-01 12:10:00 INFO User 42 logged out\n"
        )
        with open(LOG_FILE, "w") as f:
            f.write(sample)
        print(f"Created sample log: {LOG_FILE}")

    run_pipeline(log_path=LOG_FILE, db_path=DB_PATH)
