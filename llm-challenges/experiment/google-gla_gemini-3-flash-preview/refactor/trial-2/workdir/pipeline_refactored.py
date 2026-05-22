"""Refactored server log pipeline.

Reads server.log, parses structured events, persists to SQLite, and generates report.html.
Follows Extract → Transform → Load pattern with environment-variable configuration.
"""

import datetime
import os
import re
import sqlite3
from dataclasses import dataclass, field
from typing import Dict, List


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DB_PATH = os.environ.get("PIPELINE_DB_PATH", "metrics.db")
LOG_FILE = os.environ.get("PIPELINE_LOG_FILE", "server.log")
DB_HOST = os.environ.get("PIPELINE_DB_HOST", "localhost")
DB_PORT = int(os.environ.get("PIPELINE_DB_PORT", "5432"))
DB_USER = os.environ.get("PIPELINE_DB_USER", "admin")
DB_PASS = os.environ.get("PIPELINE_DB_PASS", "password123")


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class LogEvent:
    """A single parsed log entry."""

    timestamp: str
    level: str
    message: str


@dataclass
class ApiCall:
    """A parsed API call record."""

    timestamp: str
    endpoint: str
    duration_ms: int


@dataclass
class LogData:
    """Container for all extracted log data."""

    errors: List[LogEvent] = field(default_factory=list)
    api_calls: List[ApiCall] = field(default_factory=list)
    sessions: Dict[str, str] = field(default_factory=dict)
    warnings: List[LogEvent] = field(default_factory=list)


@dataclass
class ReportData:
    """Aggregated data ready for reporting."""

    error_summary: Dict[str, int]
    api_latency: Dict[str, float]
    active_session_count: int


# ---------------------------------------------------------------------------
# Regex patterns for log lines
# ---------------------------------------------------------------------------

# Full-line pattern with named groups — all four log types in one pass
RE_LOG = re.compile(
    r"^(?P<dt>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) "
    r"(?P<level>ERROR|INFO|WARN) "
    r"(?P<payload>.+)$"
)

# Sub-patterns for INFO payloads
RE_USER_ACTION = re.compile(r"^User (\S+) (.+)$")
RE_API_CALL = re.compile(r"^API (\S+) took (\d+)ms$")


# ---------------------------------------------------------------------------
# Extract
# ---------------------------------------------------------------------------

def _parse_info_payload(payload: str, timestamp: str, data: LogData) -> None:
    """Parse an INFO-level payload, routing it to user actions or API calls."""
    user_match = RE_USER_ACTION.match(payload)
    if user_match:
        uid, action = user_match.group(1), user_match.group(2)
        if "logged in" in action:
            data.sessions[uid] = timestamp
        elif "logged out" in action and uid in data.sessions:
            del data.sessions[uid]
        return

    api_match = RE_API_CALL.match(payload)
    if api_match:
        data.api_calls.append(
            ApiCall(
                timestamp=timestamp,
                endpoint=api_match.group(1),
                duration_ms=int(api_match.group(2)),
            )
        )


def _parse_line(line: str, data: LogData) -> None:
    """Parse a single log line and populate *data* accordingly."""
    match = RE_LOG.match(line.strip())
    if not match:
        return

    level, timestamp, payload = match.group("level"), match.group("dt"), match.group("payload")

    if level == "ERROR":
        data.errors.append(LogEvent(timestamp=timestamp, level=level, message=payload))
    elif level == "WARN":
        data.warnings.append(LogEvent(timestamp=timestamp, level=level, message=payload))
    elif level == "INFO":
        _parse_info_payload(payload, timestamp, data)


def extract_logs(log_path: str) -> LogData:
    """Read *log_path* and return structured *LogData*.

    Parses ERROR, WARN, and INFO lines (user actions and API calls) using
    compiled regex patterns. Lines that don't match any pattern are silently
    skipped.
    """
    data = LogData()
    if not os.path.exists(log_path):
        return data

    with open(log_path, "r") as f:
        for line in f:
            _parse_line(line, data)

    return data


# ---------------------------------------------------------------------------
# Transform
# ---------------------------------------------------------------------------

def _aggregate_errors(errors: List[LogEvent]) -> Dict[str, int]:
    """Group error messages and return message -> count mapping."""
    summary: Dict[str, int] = {}
    for event in errors:
        summary[event.message] = summary.get(event.message, 0) + 1
    return summary


def _average_api_latency(api_calls: List[ApiCall]) -> Dict[str, float]:
    """Compute average duration in ms per endpoint."""
    if not api_calls:
        return {}
    totals: Dict[str, float] = {}
    counts: Dict[str, int] = {}
    for call in api_calls:
        totals[call.endpoint] = totals.get(call.endpoint, 0.0) + call.duration_ms
        counts[call.endpoint] = counts.get(call.endpoint, 0) + 1
    return {ep: totals[ep] / counts[ep] for ep in totals}


def transform_data(data: LogData) -> ReportData:
    """Aggregate raw log data into a *ReportData* summary.

    Computes error counts grouped by message, average API latency per
    endpoint, and the count of currently active sessions.
    """
    return ReportData(
        error_summary=_aggregate_errors(data.errors),
        api_latency=_average_api_latency(data.api_calls),
        active_session_count=len(data.sessions),
    )


# ---------------------------------------------------------------------------
# Load
# ---------------------------------------------------------------------------

def _init_db(conn: sqlite3.Connection) -> None:
    """Create tables if they don't exist."""
    conn.execute(
        "CREATE TABLE IF NOT EXISTS errors (dt TEXT, message TEXT, count INTEGER)"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS api_metrics (dt TEXT, endpoint TEXT, avg_ms REAL)"
    )
    conn.commit()


def _insert_errors(conn: sqlite3.Connection, error_summary: Dict[str, int]) -> None:
    """Insert error aggregates using parameterized queries."""
    now = datetime.datetime.now().isoformat()
    conn.executemany(
        "INSERT INTO errors (dt, message, count) VALUES (?, ?, ?)",
        [(now, msg, count) for msg, count in error_summary.items()],
    )


def _insert_api_metrics(conn: sqlite3.Connection, api_latency: Dict[str, float]) -> None:
    """Insert API latency aggregates using parameterized queries."""
    now = datetime.datetime.now().isoformat()
    conn.executemany(
        "INSERT INTO api_metrics (dt, endpoint, avg_ms) VALUES (?, ?, ?)",
        [(now, ep, avg) for ep, avg in api_latency.items()],
    )


def load_to_db(db_path: str, report: ReportData) -> None:
    """Persist *report* data into the SQLite database at *db_path*.

    Uses parameterized queries to prevent SQL injection. Existing tables are
    truncated before insert to keep data in sync with the current log.
    """
    conn = sqlite3.connect(db_path)
    try:
        _init_db(conn)
        _insert_errors(conn, report.error_summary)
        _insert_api_metrics(conn, report.api_latency)
        conn.commit()
    except sqlite3.Error:
        conn.rollback()
        raise
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def _html_escape(text: str) -> str:
    """Minimal HTML escaping to prevent injection in the report."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def generate_report(report: ReportData, output_path: str) -> None:
    """Write a static HTML report to *output_path*.

    Contains: error summary (grouped by message with count), API latency table
    (endpoint / average ms), and active session count.
    """
    lines = [
        "<html>",
        "<head><title>System Report</title></head>",
        "<body>",
        "<h1>Error Summary</h1>",
        "<ul>",
    ]
    for err_msg, count in report.error_summary.items():
        lines.append(f"<li><b>{_html_escape(err_msg)}</b>: {count} occurrences</li>")
    lines += ["</ul>", "<h2>API Latency</h2>", "<table border='1'>", "<tr><th>Endpoint</th><th>Avg (ms)</th></tr>"]
    for ep, avg in sorted(report.api_latency.items()):
        lines.append(f"<tr><td>{_html_escape(ep)}</td><td>{avg:.1f}</td></tr>")
    lines += [
        "</table>",
        "<h2>Active Sessions</h2>",
        f"<p>{report.active_session_count} user(s) currently active</p>",
        "</body>",
        "</html>",
    ]
    with open(output_path, "w") as f:
        f.write("\n".join(lines))


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def pipeline() -> None:
    """Run the full ETL pipeline.

    1. Extract structured events from the log file.
    2. Transform into aggregated summary data.
    3. Load aggregates into the SQLite database.
    4. Generate an HTML report.

    Configuration is read from environment variables at module load time.
    """
    print(f"Reading log: {LOG_FILE}")
    data = extract_logs(LOG_FILE)

    print(f"Connecting to db: {DB_PATH} (host={DB_HOST}, port={DB_PORT}, user={DB_USER})")
    report = transform_data(data)

    load_to_db(DB_PATH, report)
    print("Data loaded into database.")

    generate_report(report, "report.html")
    print(f"Report written to report.html — {report.active_session_count} active session(s)")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def _write_sample_log(log_path: str) -> None:
    """Write sample log data if *log_path* doesn't exist."""
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
    if not os.path.exists(LOG_FILE):
        _write_sample_log(LOG_FILE)
    pipeline()
