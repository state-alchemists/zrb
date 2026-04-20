"""Refactored log processing pipeline.

Improvements over the original implementation:
- Configuration is read from environment variables instead of hardcoding.
- SQL operations use parameterized queries to avoid injection vulnerabilities.
- Logic is decomposed into Extract → Transform → Load stages.
- Log lines are parsed using regular expressions for robustness.
- Type hints and docstrings are provided throughout.

The generated HTML report preserves the original information:
- Error summary (message → count)
- API latency table (endpoint → average latency)
- Active session count
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import os
import re
import sqlite3
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Tuple

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class Config:
    """Application configuration sourced from environment variables.

    Environment variables (all optional; defaults preserve original behavior):
    - DB_PATH: path to the SQLite database file (default: "metrics.db").
    - LOG_FILE: path to the server log file (default: "server.log").
    - DB_HOST: hostname used only for display/logging (default: "localhost").
    - DB_PORT: port used only for display/logging (default: "5432").
    - DB_USER: username used only for display/logging (default: "admin").
    - DB_PASS: password used only for display/logging (default: "password123").
    """

    db_path: Path
    log_file: Path
    db_host: str
    db_port: int
    db_user: str
    db_pass: str


def load_config() -> Config:
    """Load configuration from environment variables.

    Defaults match the original hardcoded values so behavior is preserved
    when the variables are not set.
    """

    db_path = Path(os.getenv("DB_PATH", "metrics.db"))
    log_file = Path(os.getenv("LOG_FILE", "server.log"))
    db_host = os.getenv("DB_HOST", "localhost")
    db_port_raw = os.getenv("DB_PORT", "5432")
    db_user = os.getenv("DB_USER", "admin")
    db_pass = os.getenv("DB_PASS", "password123")

    try:
        db_port = int(db_port_raw)
    except ValueError:
        db_port = 5432

    return Config(
        db_path=db_path,
        log_file=log_file,
        db_host=db_host,
        db_port=db_port,
        db_user=db_user,
        db_pass=db_pass,
    )


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class LogRecord:
    """Structured representation of a single log line."""

    timestamp: dt.datetime
    level: str
    message: str


@dataclasses.dataclass
class ApiCall:
    """API call metric extracted from a log line."""

    timestamp: dt.datetime
    endpoint: str
    duration_ms: int


# ---------------------------------------------------------------------------
# Extract
# ---------------------------------------------------------------------------


# Example log lines (from original file):
# 2024-01-01 12:00:00 INFO User 42 logged in
# 2024-01-01 12:05:00 ERROR Database timeout
# 2024-01-01 12:08:00 INFO API /users/profile took 250ms
# 2024-01-01 12:09:00 WARN Memory usage at 87%

LOG_LINE_RE = re.compile(
    r"^(?P<date>\d{4}-\d{2}-\d{2})\s+"  # date
    r"(?P<time>\d{2}:\d{2}:\d{2})\s+"  # time
    r"(?P<level>\S+)\s+"  # level
    r"(?P<rest>.*)$"  # rest of the line
)

USER_RE = re.compile(r"User\s+(?P<user_id>\S+)\s+(?P<action>.+)")
API_RE = re.compile(
    r"API\s+(?P<endpoint>\S+)\s+" r"took\s+(?P<duration>\d+)ms",
    re.IGNORECASE,
)


def parse_log_line(line: str) -> Optional[LogRecord]:
    """Parse a single raw log line into a LogRecord.

    Returns None if the line does not match the expected format.
    """

    m = LOG_LINE_RE.match(line.strip())
    if not m:
        return None

    date_str = m.group("date")
    time_str = m.group("time")
    level = m.group("level")
    rest = m.group("rest")

    try:
        timestamp = dt.datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None

    return LogRecord(timestamp=timestamp, level=level, message=rest)


def extract_logs(path: Path) -> List[LogRecord]:
    """Read and parse all log lines from *path*.

    Missing files return an empty list, matching original behavior.
    """

    if not path.exists():
        return []

    records: List[LogRecord] = []
    with path.open("r", encoding="utf-8") as f:
        for raw_line in f:
            record = parse_log_line(raw_line)
            if record is not None:
                records.append(record)
    return records


# ---------------------------------------------------------------------------
# Transform
# ---------------------------------------------------------------------------


def build_error_summary(records: Iterable[LogRecord]) -> Dict[str, int]:
    """Aggregate error messages into a message → count mapping."""

    errors: Dict[str, int] = {}
    for rec in records:
        if rec.level == "ERROR":
            msg = rec.message.strip()
            if not msg:
                continue
            errors[msg] = errors.get(msg, 0) + 1
    return errors


def extract_sessions_and_api_calls(
    records: Iterable[LogRecord],
) -> Tuple[Dict[str, dt.datetime], List[ApiCall]]:
    """Derive active sessions and API call metrics from log records.

    The logic mirrors the original implementation:
    - Users are identified by lines containing "User <id> ...".
    - A "logged in" action opens a session; "logged out" closes it.
    - Active sessions at the end are those without a corresponding logout.
    - API lines matching the original pattern are recorded with their duration.
    """

    active_sessions: Dict[str, dt.datetime] = {}
    api_calls: List[ApiCall] = []

    for rec in records:
        # User sessions
        if rec.level == "INFO":
            user_match = USER_RE.search(rec.message)
            if user_match:
                user_id = user_match.group("user_id")
                action = user_match.group("action")
                if "logged in" in action:
                    active_sessions[user_id] = rec.timestamp
                elif "logged out" in action and user_id in active_sessions:
                    active_sessions.pop(user_id, None)

        # API metrics
        if rec.level == "INFO" and "API" in rec.message:
            api_match = API_RE.search(rec.message)
            if api_match:
                endpoint = api_match.group("endpoint")
                duration_ms = int(api_match.group("duration"))
                api_calls.append(
                    ApiCall(
                        timestamp=rec.timestamp,
                        endpoint=endpoint,
                        duration_ms=duration_ms,
                    )
                )

    return active_sessions, api_calls


def compute_endpoint_stats(api_calls: Iterable[ApiCall]) -> Dict[str, List[int]]:
    """Group API call durations by endpoint."""

    stats: Dict[str, List[int]] = {}
    for call in api_calls:
        stats.setdefault(call.endpoint, []).append(call.duration_ms)
    return stats


# ---------------------------------------------------------------------------
# Load (database + report generation)
# ---------------------------------------------------------------------------


def init_db(conn: sqlite3.Connection) -> None:
    """Create necessary tables if they do not already exist."""

    cursor = conn.cursor()
    cursor.execute(
        "CREATE TABLE IF NOT EXISTS errors (dt TEXT, message TEXT, count INTEGER)"
    )
    cursor.execute(
        "CREATE TABLE IF NOT EXISTS api_metrics (dt TEXT, endpoint TEXT, avg_ms REAL)"
    )
    conn.commit()


def load_to_db(
    conn: sqlite3.Connection,
    error_summary: Mapping[str, int],
    endpoint_stats: Mapping[str, List[int]],
    now: Optional[dt.datetime] = None,
) -> None:
    """Persist aggregates to the SQLite database using parameterized queries."""

    if now is None:
        now = dt.datetime.now()

    cursor = conn.cursor()

    # Insert error records
    for message, count in error_summary.items():
        cursor.execute(
            "INSERT INTO errors (dt, message, count) VALUES (?, ?, ?)",
            (now.isoformat(sep=" "), message, count),
        )

    # Insert API metrics
    for endpoint, durations in endpoint_stats.items():
        if not durations:
            continue
        avg_ms = sum(durations) / len(durations)
        cursor.execute(
            "INSERT INTO api_metrics (dt, endpoint, avg_ms) VALUES (?, ?, ?)",
            (now.isoformat(sep=" "), endpoint, avg_ms),
        )

    conn.commit()


def render_html_report(
    error_summary: Mapping[str, int],
    endpoint_stats: Mapping[str, List[int]],
    active_sessions: Mapping[str, dt.datetime],
) -> str:
    """Render the HTML report with the same information as the original script."""

    parts: List[str] = []
    parts.append("<html>")
    parts.append("<head><title>System Report</title></head>")
    parts.append("<body>")

    # Error summary
    parts.append("<h1>Error Summary</h1>")
    parts.append("<ul>")
    for err_msg, count in error_summary.items():
        parts.append(
            f"<li><b>{err_msg}</b>: {count} occurrences</li>"
        )
    parts.append("</ul>")

    # API latency
    parts.append("<h2>API Latency</h2>")
    parts.append("<table border='1'>")
    parts.append("<tr><th>Endpoint</th><th>Avg (ms)</th></tr>")
    for endpoint, durations in endpoint_stats.items():
        if not durations:
            continue
        avg = sum(durations) / len(durations)
        parts.append(
            f"<tr><td>{endpoint}</td><td>{round(avg, 1)}</td></tr>"
        )
    parts.append("</table>")

    # Active sessions
    parts.append("<h2>Active Sessions</h2>")
    parts.append(f"<p>{len(active_sessions)} user(s) currently active</p>")

    parts.append("</body>")
    parts.append("</html>")

    return "\n".join(parts)


def write_report(html: str, output_path: Path) -> None:
    """Write the HTML report to *output_path*."""

    output_path.write_text(html, encoding="utf-8")


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def run_pipeline(config: Config) -> None:
    """Run the full Extract → Transform → Load pipeline."""

    # Extract
    records = extract_logs(config.log_file)

    # Transform
    error_summary = build_error_summary(records)
    active_sessions, api_calls = extract_sessions_and_api_calls(records)
    endpoint_stats = compute_endpoint_stats(api_calls)

    # Show connection information (for parity with original script)
    print(
        f"Connecting to {config.db_host}:{config.db_port} as {config.db_user}..."
    )

    # Load into database
    conn = sqlite3.connect(str(config.db_path))
    try:
        init_db(conn)
        load_to_db(conn, error_summary, endpoint_stats)
    finally:
        conn.close()

    # Generate report
    html = render_html_report(error_summary, endpoint_stats, active_sessions)
    write_report(html, Path("report.html"))

    print(f"Job finished at {dt.datetime.now()}")


def _bootstrap_demo_log_file(path: Path) -> None:
    """Create a demo log file with sample content if it does not exist.

    This mirrors the behavior of the original script, which wrote a few
    sample lines when the log file was missing.
    """

    if path.exists():
        return

    sample_lines = [
        "2024-01-01 12:00:00 INFO User 42 logged in\n",
        "2024-01-01 12:05:00 ERROR Database timeout\n",
        "2024-01-01 12:05:05 ERROR Database timeout\n",
        "2024-01-01 12:08:00 INFO API /users/profile took 250ms\n",
        "2024-01-01 12:09:00 WARN Memory usage at 87%\n",
        "2024-01-01 12:10:00 INFO User 42 logged out\n",
    ]

    path.write_text("".join(sample_lines), encoding="utf-8")


if __name__ == "__main__":
    cfg = load_config()
    _bootstrap_demo_log_file(cfg.log_file)
    run_pipeline(cfg)
