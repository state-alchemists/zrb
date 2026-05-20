"""Server log processing pipeline with Extract-Transform-Load pattern.

Reads server logs, parses them with regex, aggregates error counts and API
latency metrics, persists to SQLite via parameterized queries, and generates
an HTML report.

Usage:
    export LOG_FILE=server.log
    export DB_PATH=metrics.db
    python pipeline_refactored.py
"""

import datetime
import os
import re
import sqlite3
from collections import Counter
from typing import Any, Dict, List, Tuple


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

def _get_config() -> Dict[str, str]:
    """Load configuration from environment variables with safe defaults."""
    return {
        "log_file": os.getenv("LOG_FILE", "server.log"),
        "db_path": os.getenv("DB_PATH", "metrics.db"),
        "db_host": os.getenv("DB_HOST", "localhost"),
        "db_port": os.getenv("DB_PORT", "5432"),
        "db_user": os.getenv("DB_USER", "admin"),
        "db_pass": os.getenv("DB_PASS", ""),
    }


# ---------------------------------------------------------------------------
# Regex patterns for log line parsing
# ---------------------------------------------------------------------------

_LOG_PATTERNS = {
    "ERROR": re.compile(
        r"^(?P<dt>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) ERROR (?P<message>.*)$"
    ),
    "USER": re.compile(
        r"^(?P<dt>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) INFO User (?P<uid>\S+) (?P<action>.+)$"
    ),
    "API": re.compile(
        r"^(?P<dt>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) INFO API (?P<endpoint>\S+) took (?P<ms>\d+)ms$"
    ),
    "WARN": re.compile(
        r"^(?P<dt>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) WARN (?P<message>.*)$"
    ),
}

LogEntry = Dict[str, Any]
ApiCall = Dict[str, Any]
SessionMap = Dict[str, str]


# ================================ E X T R A C T ================================

def extract_logs(log_path: str) -> Tuple[List[LogEntry], List[ApiCall], SessionMap]:
    """Read a server log file and parse every line into structured records.

    Args:
        log_path: Path to the server log file.

    Returns:
        A tuple (log_entries, api_calls, sessions):
        - log_entries: all parsed lines as dicts with keys ``dt``, ``type``,
          and type-specific payload.
        - api_calls: API latency records (``dt``, ``endpoint``, ``ms``).
        - sessions: user_id → login timestamp map rebuilt from the full log.
    """
    log_entries: List[LogEntry] = []
    api_calls: List[ApiCall] = []
    sessions: SessionMap = {}

    if not os.path.exists(log_path):
        return log_entries, api_calls, sessions

    with open(log_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            _parse_line(line, log_entries, api_calls, sessions)

    return log_entries, api_calls, sessions


def _parse_line(
    line: str,
    log_entries: List[LogEntry],
    api_calls: List[ApiCall],
    sessions: SessionMap,
) -> None:
    """Match *line* against known log patterns and append results.

    Tries ERROR, INFO User, INFO API, and WARN patterns in order. Appends
    structured dicts to the provided lists and mutates *sessions* for
    login/logout events.
    """
    # ERROR
    match = _LOG_PATTERNS["ERROR"].match(line)
    if match:
        log_entries.append({
            "dt": match.group("dt"),
            "type": "ERR",
            "message": match.group("message").strip(),
        })
        return

    # INFO User (login / logout)
    match = _LOG_PATTERNS["USER"].match(line)
    if match:
        uid = match.group("uid")
        action = match.group("action").strip()
        dt = match.group("dt")
        if "logged in" in action:
            sessions[uid] = dt
        elif "logged out" in action and uid in sessions:
            sessions.pop(uid, None)
        log_entries.append({
            "dt": dt,
            "type": "USR",
            "uid": uid,
            "action": action,
        })
        return

    # INFO API (latency measurement)
    match = _LOG_PATTERNS["API"].match(line)
    if match:
        entry = {
            "dt": match.group("dt"),
            "endpoint": match.group("endpoint"),
            "ms": int(match.group("ms")),
        }
        api_calls.append(entry)
        log_entries.append({"dt": entry["dt"], "type": "API", **entry})
        return

    # WARN
    match = _LOG_PATTERNS["WARN"].match(line)
    if match:
        log_entries.append({
            "dt": match.group("dt"),
            "type": "WARN",
            "message": match.group("message").strip(),
        })


# ================================ T R A N S F O R M ================================

def transform_errors(log_entries: List[LogEntry]) -> Counter:
    """Aggregate error counts from parsed log entries.

    Args:
        log_entries: Parsed entries from :func:`extract_logs`.

    Returns:
        A Counter mapping each unique error message to its occurrence count.
    """
    return Counter(
        entry["message"]
        for entry in log_entries
        if entry["type"] == "ERR"
    )


def transform_api_latency(api_calls: List[ApiCall]) -> Dict[str, float]:
    """Compute average latency per API endpoint.

    Args:
        api_calls: API call records from :func:`extract_logs`.

    Returns:
        Mapping of endpoint name → average latency in milliseconds.
    """
    stats: Dict[str, List[int]] = {}
    for call in api_calls:
        stats.setdefault(call["endpoint"], []).append(call["ms"])
    return {ep: sum(times) / len(times) for ep, times in stats.items()}


# ================================ L O A D ================================

def load_database(
    db_path: str,
    error_counts: Counter,
    api_latencies: Dict[str, float],
) -> None:
    """Persist error counts and API latency metrics to SQLite.

    Creates tables if they do not exist and inserts rows using parameterized
    queries to prevent SQL injection.

    Args:
        db_path: Filesystem path for the SQLite database.
        error_counts: Error-message → count mapping.
        api_latencies: Endpoint → average-ms mapping.
    """
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            "CREATE TABLE IF NOT EXISTS errors "
            "(dt TEXT, message TEXT, count INTEGER)"
        )
        cur.execute(
            "CREATE TABLE IF NOT EXISTS api_metrics "
            "(dt TEXT, endpoint TEXT, avg_ms REAL)"
        )

        now = datetime.datetime.now().isoformat()

        cur.executemany(
            "INSERT INTO errors (dt, message, count) VALUES (?, ?, ?)",
            [(now, msg, cnt) for msg, cnt in error_counts.items()],
        )
        cur.executemany(
            "INSERT INTO api_metrics (dt, endpoint, avg_ms) VALUES (?, ?, ?)",
            [(now, ep, avg) for ep, avg in api_latencies.items()],
        )

        conn.commit()
    finally:
        conn.close()


def load_html_report(
    error_counts: Counter,
    api_latencies: Dict[str, float],
    active_session_count: int,
    output_path: str = "report.html",
) -> None:
    """Generate an HTML report with error summary, API latency table,
    and active session count.

    Args:
        error_counts: Error-message → count mapping.
        api_latencies: Endpoint → average-ms mapping.
        active_session_count: Number of currently logged-in users.
        output_path: Destination path for the HTML file.
    """
    lines = [
        "<!DOCTYPE html>",
        "<html>",
        "<head><title>System Report</title></head>",
        "<body>",
        "<h1>Error Summary</h1>",
        "<ul>",
    ]
    for err_msg, count in sorted(error_counts.items(), key=lambda x: -x[1]):
        lines.append(
            f"<li><b>{_html_escape(err_msg)}</b>: {count} occurrences</li>"
        )
    lines.append("</ul>")

    lines.append("<h2>API Latency</h2>")
    lines.append("<table border='1'>")
    lines.append("<tr><th>Endpoint</th><th>Avg (ms)</th></tr>")
    for ep, avg in sorted(api_latencies.items(), key=lambda x: -x[1]):
        lines.append(
            f"<tr><td>{_html_escape(ep)}</td><td>{avg:.1f}</td></tr>"
        )
    lines.append("</table>")

    lines.append("<h2>Active Sessions</h2>")
    lines.append(f"<p>{active_session_count} user(s) currently active</p>")
    lines.append("</body>")
    lines.append("</html>")

    with open(output_path, "w") as f:
        f.write("\n".join(lines) + "\n")


def _html_escape(text: str) -> str:
    """Escape HTML special characters to prevent content injection."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


# ================================ P I P E L I N E ================================

def run_pipeline() -> None:
    """Execute the full Extract → Transform → Load pipeline.

    Reads config from environment variables, processes the log file, persists
    metrics to SQLite, and produces an HTML report.
    """
    config = _get_config()

    print(
        f"Connecting to {config['db_host']}:{config['db_port']} "
        f"as {config['db_user']}..."
    )

    # Extract
    log_entries, api_calls, sessions = extract_logs(config["log_file"])

    # Transform
    error_counts = transform_errors(log_entries)
    api_latencies = transform_api_latency(api_calls)

    # Load
    load_database(config["db_path"], error_counts, api_latencies)
    load_html_report(
        error_counts=error_counts,
        api_latencies=api_latencies,
        active_session_count=len(sessions),
    )

    print(f"Job finished at {datetime.datetime.now()}")


def _seed_sample_log(log_path: str) -> None:
    """Write sample log lines if the log file does not exist."""
    lines = [
        "2024-01-01 12:00:00 INFO User 42 logged in",
        "2024-01-01 12:05:00 ERROR Database timeout",
        "2024-01-01 12:05:05 ERROR Database timeout",
        "2024-01-01 12:08:00 INFO API /users/profile took 250ms",
        "2024-01-01 12:09:00 WARN Memory usage at 87%",
        "2024-01-01 12:10:00 INFO User 42 logged out",
    ]
    with open(log_path, "w") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    log_file = _get_config()["log_file"]
    if not os.path.exists(log_file):
        _seed_sample_log(log_file)
    run_pipeline()
