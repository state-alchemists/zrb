"""Server log processing pipeline with Extract → Transform → Load pattern.

Extracts structured data from server logs, transforms/aggregates metrics,
and loads results into SQLite + an HTML report.

Usage:
    export METRICS_DB_PATH="metrics.db"
    export SERVER_LOG_PATH="server.log"
    python pipeline_refactored.py
"""

import datetime
import os
import re
import sqlite3
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Configuration (all from environment variables)
# ---------------------------------------------------------------------------

def _get_config() -> Dict[str, str]:
    """Load configuration from environment variables with defaults."""
    return {
        "db_path": os.getenv("METRICS_DB_PATH", "metrics.db"),
        "log_path": os.getenv("SERVER_LOG_PATH", "server.log"),
        "db_host": os.getenv("DB_HOST", "localhost"),
        "db_port": os.getenv("DB_PORT", "5432"),
        "db_user": os.getenv("DB_USER", "admin"),
        "db_pass": os.getenv("DB_PASS", "password123"),
    }


# ---------------------------------------------------------------------------
# Model types
# ---------------------------------------------------------------------------

LogEntry = Dict[str, Any]         # {"dt": str, "type": str, ...}
ApiCall = Dict[str, Any]          # {"dt": str, "endpoint": str, "ms": int}
SessionMap = Dict[str, str]       # user_id -> login_timestamp


# ---------------------------------------------------------------------------
# Regex patterns for log line parsing
# ---------------------------------------------------------------------------

_ERROR_RE = re.compile(
    r"^(?P<dt>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) ERROR (?P<message>.*)$"
)
_INFO_USER_RE = re.compile(
    r"^(?P<dt>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) INFO User (?P<uid>\S+) (?P<action>.+)$"
)
_INFO_API_RE = re.compile(
    r"^(?P<dt>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) INFO API (?P<endpoint>\S+) took (?P<ms>\d+)ms$"
)
_WARN_RE = re.compile(
    r"^(?P<dt>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) WARN (?P<message>.*)$"
)


# ================================ E X T R A C T ================================

def extract_logs(log_path: str) -> Tuple[List[LogEntry], List[ApiCall], SessionMap]:
    """Read and parse a server log file, returning structured records.

    Args:
        log_path: Path to the server log file.

    Returns:
        A tuple of (log_entries, api_calls, active_sessions).
        - log_entries: Every parsed line as a dict with keys ``dt``, ``type``, and
          the type-specific payload keys.
        - api_calls: API latency records (``dt``, ``endpoint``, ``ms``).
        - active_sessions: Current active session map (user_id -> login timestamp)
          rebuilt from the complete log.
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
    """Match *line* against known patterns and append results to the output lists."""

    # --- ERROR ---
    m = _ERROR_RE.match(line)
    if m:
        log_entries.append({
            "dt": m.group("dt"),
            "type": "ERR",
            "message": m.group("message").strip(),
        })
        return

    # --- INFO User (login / logout) ---
    m = _INFO_USER_RE.match(line)
    if m:
        uid = m.group("uid")
        action = m.group("action").strip()
        dt = m.group("dt")
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

    # --- INFO API (latency measurement) ---
    m = _INFO_API_RE.match(line)
    if m:
        api_calls.append({
            "dt": m.group("dt"),
            "endpoint": m.group("endpoint"),
            "ms": int(m.group("ms")),
        })
        log_entries.append({
            "dt": m.group("dt"),
            "type": "API",
            "endpoint": m.group("endpoint"),
            "ms": int(m.group("ms")),
        })
        return

    # --- WARN ---
    m = _WARN_RE.match(line)
    if m:
        log_entries.append({
            "dt": m.group("dt"),
            "type": "WARN",
            "message": m.group("message").strip(),
        })
        return


# ================================ T R A N S F O R M ================================

def transform_errors(log_entries: List[LogEntry]) -> Counter:
    """Count occurrences of each unique error message.

    Args:
        log_entries: Parsed log entries from :func:`extract_logs`.

    Returns:
        A Counter mapping error message text → occurrence count.
    """
    return Counter(
        entry["message"]
        for entry in log_entries
        if entry["type"] == "ERR"
    )


def transform_api_latency(api_calls: List[ApiCall]) -> Dict[str, float]:
    """Compute average latency per API endpoint.

    Args:
        api_calls: List of API call records with ``endpoint`` and ``ms``.

    Returns:
        Mapping of endpoint → average latency in milliseconds.
    """
    stats: Dict[str, List[int]] = {}
    for call in api_calls:
        stats.setdefault(call["endpoint"], []).append(call["ms"])
    return {
        ep: sum(times) / len(times)
        for ep, times in stats.items()
    }


# ================================ L O A D ================================

def load_database(
    db_path: str,
    error_counts: Counter,
    api_latencies: Dict[str, float],
) -> None:
    """Write aggregated metrics into a SQLite database.

    Args:
        db_path: Filesystem path for the SQLite database.
        error_counts: Error-message → count mapping.
        api_latencies: Endpoint → average-ms mapping.

    Uses parameterized queries to prevent SQL injection.
    """
    conn = sqlite3.connect(db_path)
    try:
        c = conn.cursor()
        c.execute(
            "CREATE TABLE IF NOT EXISTS errors "
            "(dt TEXT, message TEXT, count INTEGER)"
        )
        c.execute(
            "CREATE TABLE IF NOT EXISTS api_metrics "
            "(dt TEXT, endpoint TEXT, avg_ms REAL)"
        )

        now = datetime.datetime.now().isoformat()

        c.executemany(
            "INSERT INTO errors (dt, message, count) VALUES (?, ?, ?)",
            [(now, msg, cnt) for msg, cnt in error_counts.items()],
        )
        c.executemany(
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
        output_path: Destination path for the generated HTML file.
    """
    lines: List[str] = [
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
            f"<tr><td>{_html_escape(ep)}</td>"
            f"<td>{avg:.1f}</td></tr>"
        )
    lines.append("</table>")

    lines.append("<h2>Active Sessions</h2>")
    lines.append(f"<p>{active_session_count} user(s) currently active</p>")
    lines.append("</body>")
    lines.append("</html>")

    with open(output_path, "w") as f:
        f.write("\n".join(lines) + "\n")


def _html_escape(text: str) -> str:
    """Minimal HTML escaping — prevents content-injection in report output."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


# ================================ P I P E L I N E ================================

def run_pipeline() -> None:
    """Execute the full Extract → Transform → Load pipeline.

    Reads config from environment variables, processes the log file, writes
    metrics to the database and generates an HTML report.
    """
    config = _get_config()

    print(
        f"Connecting to {config['db_host']}:{config['db_port']} "
        f"as {config['db_user']}..."
    )

    # --- Extract ---
    log_entries, api_calls, sessions = extract_logs(config["log_path"])

    # --- Transform ---
    error_counts = transform_errors(log_entries)
    api_latencies = transform_api_latency(api_calls)

    # --- Load ---
    load_database(config["db_path"], error_counts, api_latencies)
    load_html_report(
        error_counts=error_counts,
        api_latencies=api_latencies,
        active_session_count=len(sessions),
    )

    print(f"Job finished at {datetime.datetime.now()}")


# ================================ S E E D I N G ================================

def _seed_sample_log(log_path: str) -> None:
    """Write sample log lines if the log file does not yet exist.

    Args:
        log_path: Path to write the sample data to.
    """
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
    config = _get_config()
    if not os.path.exists(config["log_path"]):
        _seed_sample_log(config["log_path"])
    run_pipeline()
