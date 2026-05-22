"""Server log pipeline: extract → transform → load.

Reads server logs, parses them into structured records, aggregates
error counts and API latency metrics, stores results in SQLite,
and emits an HTML report.
"""

import datetime
import html
import os
import re
import sqlite3
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass
class Config:
    """Application configuration loaded from environment variables.

    Attributes:
        db_path:   Path to the SQLite database file.
        log_path:  Path to the server log file.
        db_host:   Database server hostname (informational for SQLite).
        db_port:   Database server port (informational for SQLite).
        db_user:   Database username (informational for SQLite).
        db_pass:   Database password (informational for SQLite).
    """

    db_path: str
    log_path: str
    db_host: str = "localhost"
    db_port: int = 5432
    db_user: str = "admin"
    db_pass: str = ""


def load_config() -> Config:
    """Read configuration from environment variables prefixed with ``LOG_PIPELINE_``."""
    return Config(
        db_path=os.getenv("LOG_PIPELINE_DB_PATH", "metrics.db"),
        log_path=os.getenv("LOG_PIPELINE_LOG_PATH", "server.log"),
        db_host=os.getenv("LOG_PIPELINE_DB_HOST", "localhost"),
        db_port=int(os.getenv("LOG_PIPELINE_DB_PORT", "5432")),
        db_user=os.getenv("LOG_PIPELINE_DB_USER", "admin"),
        db_pass=os.getenv("LOG_PIPELINE_DB_PASS", ""),
    )


# ---------------------------------------------------------------------------
# Extract — regex-based log parsing
# ---------------------------------------------------------------------------

_LOG_LINE_RE = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) "
    r"(?P<level>ERROR|INFO|WARN) "
    r"(?P<message>.+)$"
)

_USER_ACTION_RE = re.compile(r"^User (?P<uid>\d+) (?P<action>.+)$")

_API_CALL_RE = re.compile(
    r"^API (?P<endpoint>\S+).*?(?:took (?P<duration>\d+)ms)?$"
)


def parse_log_line(line: str) -> Optional[Dict[str, Any]]:
    """Parse a single log line into a structured dictionary.

    Returns ``None`` for lines that don't match the expected format.

    Recognised entry types:

    * ``error`` — keys: ``timestamp``, ``message``
    * ``warn``  — keys: ``timestamp``, ``message``
    * ``user``  — keys: ``timestamp``, ``uid``, ``action``, ``logged_in``
    * ``api``   — keys: ``timestamp``, ``endpoint``, ``duration_ms``
    """
    match = _LOG_LINE_RE.match(line.strip())
    if not match:
        return None

    ts = match.group("timestamp")
    level = match.group("level")
    msg = match.group("message")

    if level == "ERROR":
        return {"type": "error", "timestamp": ts, "message": msg}

    if level == "WARN":
        return {"type": "warn", "timestamp": ts, "message": msg}

    # INFO — check for user action or API call
    user_match = _USER_ACTION_RE.match(msg)
    if user_match:
        uid = user_match.group("uid")
        action = user_match.group("action")
        return {
            "type": "user",
            "timestamp": ts,
            "uid": uid,
            "action": action,
            "logged_in": "logged in" in action,
        }

    api_match = _API_CALL_RE.match(msg)
    if api_match:
        duration_str = api_match.group("duration")
        return {
            "type": "api",
            "timestamp": ts,
            "endpoint": api_match.group("endpoint"),
            "duration_ms": int(duration_str) if duration_str else 0,
        }

    return None


def extract_logs(log_path: str) -> List[Dict[str, Any]]:
    """Read and parse all log entries from *log_path*.

    Malformed lines are silently skipped.
    """
    if not os.path.exists(log_path):
        return []

    entries: List[Dict[str, Any]] = []
    with open(log_path, "r") as f:
        for line in f:
            parsed = parse_log_line(line)
            if parsed is not None:
                entries.append(parsed)
    return entries


# ---------------------------------------------------------------------------
# Transform
# ---------------------------------------------------------------------------


def aggregate_errors(entries: List[Dict[str, Any]]) -> Dict[str, int]:
    """Count occurrences of each unique error message."""
    counts: Dict[str, int] = {}
    for entry in entries:
        if entry.get("type") == "error":
            msg: str = entry["message"]
            counts[msg] = counts.get(msg, 0) + 1
    return counts


def compute_api_latency(entries: List[Dict[str, Any]]) -> Dict[str, float]:
    """Compute average latency (ms) per API endpoint."""
    durations: Dict[str, List[int]] = {}
    for entry in entries:
        if entry.get("type") == "api":
            ep: str = entry["endpoint"]
            durations.setdefault(ep, []).append(entry["duration_ms"])

    return {ep: sum(times) / len(times) for ep, times in durations.items()}


def count_active_sessions(entries: List[Dict[str, Any]]) -> int:
    """Track login/logout events and return current active session count."""
    active: Set[str] = set()
    for entry in entries:
        if entry.get("type") == "user":
            uid: str = entry["uid"]
            if entry["logged_in"]:
                active.add(uid)
            else:
                active.discard(uid)
    return len(active)


# ---------------------------------------------------------------------------
# Load — database
# ---------------------------------------------------------------------------


def init_db(db_path: str) -> sqlite3.Connection:
    """Open a SQLite connection and create tables if they don't exist."""
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


def insert_errors(conn: sqlite3.Connection, errors: Dict[str, int]) -> None:
    """Write aggregated error counts to the ``errors`` table.

    Uses parameterised queries to prevent SQL injection.
    """
    now = str(datetime.datetime.now())
    conn.executemany(
        "INSERT INTO errors (dt, message, count) VALUES (?, ?, ?)",
        [(now, msg, count) for msg, count in errors.items()],
    )
    conn.commit()


def insert_api_metrics(
    conn: sqlite3.Connection, latency: Dict[str, float]
) -> None:
    """Write API latency averages to the ``api_metrics`` table.

    Uses parameterised queries to prevent SQL injection.
    """
    now = str(datetime.datetime.now())
    conn.executemany(
        "INSERT INTO api_metrics (dt, endpoint, avg_ms) VALUES (?, ?, ?)",
        [(now, ep, avg) for ep, avg in latency.items()],
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Load — HTML report
# ---------------------------------------------------------------------------


def _build_error_summary(errors: Dict[str, int]) -> List[str]:
    """Build the HTML fragment for the error summary section."""
    lines: List[str] = ["<h1>Error Summary</h1>", "<ul>"]
    for err_msg, count in errors.items():
        safe_msg = html.escape(err_msg)
        lines.append(f"<li><b>{safe_msg}</b>: {count} occurrences</li>")
    lines.append("</ul>")
    return lines


def _build_api_latency_table(latency: Dict[str, float]) -> List[str]:
    """Build the HTML fragment for the API latency table."""
    lines: List[str] = [
        "<h2>API Latency</h2>",
        "<table border='1'>",
        "<tr><th>Endpoint</th><th>Avg (ms)</th></tr>",
    ]
    for ep, avg in latency.items():
        safe_ep = html.escape(ep)
        lines.append(f"<tr><td>{safe_ep}</td><td>{round(avg, 1)}</td></tr>")
    lines.append("</table>")
    return lines


def generate_report(
    errors: Dict[str, int],
    api_latency: Dict[str, float],
    active_sessions: int,
) -> str:
    """Build a complete HTML report page from the aggregated metrics."""
    parts: List[str] = [
        "<html>",
        "<head><title>System Report</title></head>",
        "<body>",
    ]
    parts.extend(_build_error_summary(errors))
    parts.extend(_build_api_latency_table(api_latency))
    parts.append("<h2>Active Sessions</h2>")
    parts.append(f"<p>{active_sessions} user(s) currently active</p>")
    parts.append("</body>")
    parts.append("</html>")
    return "\n".join(parts)


def write_report(html_content: str, output_path: str) -> None:
    """Write the HTML report to *output_path*."""
    with open(output_path, "w") as f:
        f.write(html_content)


# ---------------------------------------------------------------------------
# Pipeline orchestration
# ---------------------------------------------------------------------------


def run_pipeline(config: Config) -> None:
    """Execute the full ETL pipeline: extract → transform → load."""
    print(
        f"Connecting to {config.db_host}:{config.db_port} "
        f"as {config.db_user}..."
    )

    # Extract
    entries = extract_logs(config.log_path)

    # Transform
    errors = aggregate_errors(entries)
    api_latency = compute_api_latency(entries)
    active = count_active_sessions(entries)

    # Load — database
    conn = init_db(config.db_path)
    try:
        insert_errors(conn, errors)
        insert_api_metrics(conn, api_latency)
    finally:
        conn.close()

    # Load — HTML report
    html_report = generate_report(errors, api_latency, active)
    write_report(html_report, "report.html")

    print(f"Job finished at {datetime.datetime.now()}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def _seed_sample_log(config: Config) -> None:
    """Create a sample log file if one doesn't exist."""
    with open(config.log_path, "w") as f:
        f.write(
            "2024-01-01 12:00:00 INFO User 42 logged in\n"
            "2024-01-01 12:05:00 ERROR Database timeout\n"
            "2024-01-01 12:05:05 ERROR Database timeout\n"
            "2024-01-01 12:08:00 INFO API /users/profile took 250ms\n"
            "2024-01-01 12:09:00 WARN Memory usage at 87%\n"
            "2024-01-01 12:10:00 INFO User 42 logged out\n"
        )


if __name__ == "__main__":
    cfg = load_config()
    if not os.path.exists(cfg.log_path):
        _seed_sample_log(cfg)
    run_pipeline(cfg)
