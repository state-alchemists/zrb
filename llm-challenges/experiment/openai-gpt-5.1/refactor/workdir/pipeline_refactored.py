"""Refactored log processing pipeline.

Extract -> Transform -> Load pipeline that reads application server logs,
aggregates error counts, API latency, and active sessions, stores aggregates
into SQLite, and renders an HTML report (report.html).

Configuration is provided via environment variables:
- DB_PATH: path to SQLite database file (default: metrics.db)
- LOG_FILE: path to server log file (default: server.log)

Placeholders for future expansion (not used by sqlite3 but kept for
compatibility with the original script):
- DB_HOST, DB_PORT, DB_USER, DB_PASS
"""

from __future__ import annotations

import datetime as dt
import os
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Config:
    """Runtime configuration loaded from environment variables.

    Attributes
    ----------
    db_path:
        Filesystem path to the SQLite database file.
    log_file:
        Filesystem path to the server log file.
    db_host, db_port, db_user, db_pass:
        Additional connection attributes kept for compatibility with the
        original script's logging. They are not used by sqlite3 but may be
        useful if the implementation is later migrated to a real DB server.
    """

    db_path: Path
    log_file: Path
    db_host: str
    db_port: int
    db_user: str
    db_pass: str


def load_config() -> Config:
    """Load configuration from environment variables with sane defaults."""

    db_path = Path(os.getenv("DB_PATH", "metrics.db"))
    log_file = Path(os.getenv("LOG_FILE", "server.log"))

    db_host = os.getenv("DB_HOST", "localhost")
    db_port_str = os.getenv("DB_PORT", "5432")
    db_user = os.getenv("DB_USER", "admin")
    db_pass = os.getenv("DB_PASS", "password123")

    try:
        db_port = int(db_port_str)
    except ValueError:
        raise ValueError(f"Invalid DB_PORT value: {db_port_str!r}") from None

    return Config(
        db_path=db_path,
        log_file=log_file,
        db_host=db_host,
        db_port=db_port,
        db_user=db_user,
        db_pass=db_pass,
    )


# ---------------------------------------------------------------------------
# Extract
# ---------------------------------------------------------------------------


LOG_LINE_PATTERN = re.compile(
    r"^(?P<date>\d{4}-\d{2}-\d{2})\s+"  # date
    r"(?P<time>\d{2}:\d{2}:\d{2})\s+"      # time
    r"(?P<level>INFO|ERROR|WARN)\s+"        # log level
    r"(?P<message>.*)$"                      # message
)

USER_PATTERN = re.compile(r"User\s+(?P<user_id>\S+)\s+(?P<action>.*)")
API_PATTERN = re.compile(r"API\s+(?P<endpoint>\S+)\s+took\s+(?P<ms>\d+)ms")


@dataclass
class ParsedLog:
    """Structured representation of a single log record used by the pipeline."""

    timestamp: dt.datetime
    level: str
    message: str
    user_id: Optional[str] = None
    user_action: Optional[str] = None
    api_endpoint: Optional[str] = None
    api_duration_ms: Optional[int] = None


def parse_log_line(line: str) -> Optional[ParsedLog]:
    """Parse a single log line using regular expressions.

    The function is intentionally conservative: if the line does not match the
    expected structure it returns ``None`` and the caller can decide how to
    handle it.
    """

    line = line.rstrip("\n")
    if not line:
        return None

    m = LOG_LINE_PATTERN.match(line)
    if not m:
        return None

    date_str = m.group("date")
    time_str = m.group("time")
    level = m.group("level")
    message = m.group("message")

    timestamp = dt.datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M:%S")

    user_id: Optional[str] = None
    user_action: Optional[str] = None
    api_endpoint: Optional[str] = None
    api_duration_ms: Optional[int] = None

    # User activity lines, e.g. "User 42 logged in"
    user_match = USER_PATTERN.search(message)
    if user_match:
        user_id = user_match.group("user_id")
        user_action = user_match.group("action").strip()

    # API latency lines, e.g. "API /users/profile took 250ms"
    api_match = API_PATTERN.search(message)
    if api_match:
        api_endpoint = api_match.group("endpoint")
        api_duration_ms = int(api_match.group("ms"))

    return ParsedLog(
        timestamp=timestamp,
        level=level,
        message=message,
        user_id=user_id,
        user_action=user_action,
        api_endpoint=api_endpoint,
        api_duration_ms=api_duration_ms,
    )


def extract_logs(log_path: Path) -> List[ParsedLog]:
    """Read and parse all log lines from ``log_path``.

    Returns only successfully parsed lines.
    """

    parsed: List[ParsedLog] = []
    if not log_path.exists():
        return parsed

    with log_path.open("r", encoding="utf-8") as f:
        for line in f:
            record = parse_log_line(line)
            if record is not None:
                parsed.append(record)

    return parsed


# ---------------------------------------------------------------------------
# Transform
# ---------------------------------------------------------------------------


def aggregate_errors(records: Iterable[ParsedLog]) -> Dict[str, int]:
    """Aggregate error messages and their occurrence counts."""

    counts: Dict[str, int] = {}
    for rec in records:
        if rec.level == "ERROR":
            counts[rec.message] = counts.get(rec.message, 0) + 1
    return counts


def aggregate_api_latency(records: Iterable[ParsedLog]) -> Dict[str, List[int]]:
    """Group API call durations by endpoint."""

    stats: Dict[str, List[int]] = {}
    for rec in records:
        if rec.api_endpoint is not None and rec.api_duration_ms is not None:
            stats.setdefault(rec.api_endpoint, []).append(rec.api_duration_ms)
    return stats


def compute_active_sessions(records: Iterable[ParsedLog]) -> int:
    """Compute the number of active user sessions.

    A user is considered active if there is a "logged in" action without a
    corresponding "logged out" action later in the log.
    """

    sessions: Dict[str, dt.datetime] = {}
    for rec in records:
        if rec.user_id is None or rec.user_action is None:
            continue
        action = rec.user_action
        uid = rec.user_id
        if "logged in" in action:
            sessions[uid] = rec.timestamp
        elif "logged out" in action and uid in sessions:
            sessions.pop(uid)
    return len(sessions)


# ---------------------------------------------------------------------------
# Load (database + report rendering)
# ---------------------------------------------------------------------------


def init_db(conn: sqlite3.Connection) -> None:
    """Create required tables if they do not exist."""

    cursor = conn.cursor()
    cursor.execute(
        "CREATE TABLE IF NOT EXISTS errors (dt TEXT, message TEXT, count INTEGER)"
    )
    cursor.execute(
        "CREATE TABLE IF NOT EXISTS api_metrics (dt TEXT, endpoint TEXT, avg_ms REAL)"
    )
    conn.commit()


def load_aggregates_into_db(
    conn: sqlite3.Connection,
    error_counts: Dict[str, int],
    api_stats: Dict[str, List[int]],
    now: Optional[dt.datetime] = None,
) -> None:
    """Persist aggregated metrics into the SQLite database using safe queries."""

    if now is None:
        now = dt.datetime.now()

    cursor = conn.cursor()

    for message, count in error_counts.items():
        cursor.execute(
            "INSERT INTO errors (dt, message, count) VALUES (?, ?, ?)",
            (now.isoformat(sep=" ", timespec="seconds"), message, count),
        )

    for endpoint, durations in api_stats.items():
        if not durations:
            continue
        avg_ms = sum(durations) / len(durations)
        cursor.execute(
            "INSERT INTO api_metrics (dt, endpoint, avg_ms) VALUES (?, ?, ?)",
            (now.isoformat(sep=" ", timespec="seconds"), endpoint, avg_ms),
        )

    conn.commit()


def render_report_html(
    error_counts: Dict[str, int],
    api_stats: Dict[str, List[int]],
    active_sessions: int,
) -> str:
    """Render the HTML report preserving the original structure/content."""

    html_parts: List[str] = []
    html_parts.append("<html>")
    html_parts.append("<head><title>System Report</title></head>")
    html_parts.append("<body>")

    # Error summary
    html_parts.append("<h1>Error Summary</h1>")
    html_parts.append("<ul>")
    for err_msg, count in error_counts.items():
        html_parts.append(
            f"<li><b>{err_msg}</b>: {count} occurrences</li>"
        )
    html_parts.append("</ul>")

    # API latency table
    html_parts.append("<h2>API Latency</h2>")
    html_parts.append("<table border='1'>")
    html_parts.append("<tr><th>Endpoint</th><th>Avg (ms)</th></tr>")
    for endpoint, durations in api_stats.items():
        if not durations:
            continue
        avg = sum(durations) / len(durations)
        html_parts.append(
            f"<tr><td>{endpoint}</td><td>{round(avg, 1)}</td></tr>"
        )
    html_parts.append("</table>")

    # Active sessions
    html_parts.append("<h2>Active Sessions</h2>")
    html_parts.append(f"<p>{active_sessions} user(s) currently active</p>")

    html_parts.append("</body>")
    html_parts.append("</html>")

    return "\n".join(html_parts) + "\n"


def run_pipeline(config: Config) -> None:
    """Execute the full Extract -> Transform -> Load pipeline."""

    # Extract
    records = extract_logs(config.log_file)

    # Transform
    error_counts = aggregate_errors(records)
    api_stats = aggregate_api_latency(records)
    active_sessions = compute_active_sessions(records)

    # Log connection details (for parity with original script)
    print(
        "Connecting to "
        f"{config.db_host}:{config.db_port} as {config.db_user}..."
    )

    # Load into database
    conn = sqlite3.connect(str(config.db_path))
    try:
        init_db(conn)
        load_aggregates_into_db(conn, error_counts, api_stats)
    finally:
        conn.close()

    # Render and write report
    html = render_report_html(error_counts, api_stats, active_sessions)
    with open("report.html", "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Job finished at {dt.datetime.now()}")


def _write_sample_log_if_missing(log_path: Path) -> None:
    """Replicate the original script's behavior of creating a sample log."""

    if log_path.exists():
        return

    lines = [
        "2024-01-01 12:00:00 INFO User 42 logged in\n",
        "2024-01-01 12:05:00 ERROR Database timeout\n",
        "2024-01-01 12:05:05 ERROR Database timeout\n",
        "2024-01-01 12:08:00 INFO API /users/profile took 250ms\n",
        "2024-01-01 12:09:00 WARN Memory usage at 87%\n",
        "2024-01-01 12:10:00 INFO User 42 logged out\n",
    ]

    log_path.write_text("".join(lines), encoding="utf-8")


if __name__ == "__main__":
    cfg = load_config()
    _write_sample_log_if_missing(cfg.log_file)
    run_pipeline(cfg)
