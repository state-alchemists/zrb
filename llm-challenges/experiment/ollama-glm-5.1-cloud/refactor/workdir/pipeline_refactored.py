"""Server log processing pipeline: Extract → Transform → Load.

Reads server logs, computes error summaries and API latency stats,
persists results to SQLite, and generates an HTML report.

All configuration is read from environment variables with sensible defaults
for local development.  Set PIPELINE_DB_PASS explicitly in production.
"""

import datetime
import os
import re
import sqlite3
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

# ---------------------------------------------------------------------------
# Configuration — all via environment variables
# ---------------------------------------------------------------------------
DB_PATH: str = os.environ.get("PIPELINE_DB_PATH", "metrics.db")
LOG_FILE: str = os.environ.get("PIPELINE_LOG_FILE", "server.log")
REPORT_PATH: str = os.environ.get("PIPELINE_REPORT_PATH", "report.html")
DB_HOST: str = os.environ.get("PIPELINE_DB_HOST", "localhost")
DB_PORT: str = os.environ.get("PIPELINE_DB_PORT", "5432")
DB_USER: str = os.environ.get("PIPELINE_DB_USER", "admin")
DB_PASS: str = os.environ.get("PIPELINE_DB_PASS", "")

# ---------------------------------------------------------------------------
# Compiled regex patterns for log-line parsing
# ---------------------------------------------------------------------------
# General log line: "2024-01-01 12:05:00 ERROR Database timeout"
_LOG_RE = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s+(?P<level>\w+)\s+(?P<rest>.*)$"
)
# User event: "User 42 logged in"
_USER_RE = re.compile(r"^User\s+(?P<user_id>\S+)\s+(?P<action>.+)$")
# API call: "API /users/profile took 250ms"
_API_RE = re.compile(r"^API\s+(?P<endpoint>\S+)(?:\s+took\s+(?P<ms>\d+)ms)?$")


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------
@dataclass
class LogEntry:
    """A general log entry (ERROR / WARN)."""
    timestamp: str
    level: str
    message: str


@dataclass
class UserEvent:
    """A user session event (login / logout)."""
    timestamp: str
    user_id: str
    action: str


@dataclass
class ApiCall:
    """An API call with its latency in milliseconds."""
    timestamp: str
    endpoint: str
    ms: int


@dataclass
class TransformedData:
    """Aggregated results ready for database loading and report generation."""
    error_summary: Dict[str, int] = field(default_factory=dict)
    api_latency: Dict[str, List[int]] = field(default_factory=dict)
    active_sessions: Dict[str, str] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Extract
# ---------------------------------------------------------------------------
def extract_log_entries(
    log_file: str,
) -> Tuple[List[LogEntry], List[UserEvent], List[ApiCall]]:
    """Parse a server log file into structured records.

    Uses compiled regex patterns instead of fragile string splitting so that
    minor format variations (extra whitespace, longer messages) are handled
    gracefully.

    Args:
        log_file: Path to the server log file.

    Returns:
        A 3-tuple of ``(log_entries, user_events, api_calls)``.
    """
    entries: List[LogEntry] = []
    user_events: List[UserEvent] = []
    api_calls: List[ApiCall] = []

    if not os.path.exists(log_file):
        print(f"Log file '{log_file}' not found; returning empty data.")
        return entries, user_events, api_calls

    with open(log_file, "r") as fh:
        for line in fh:
            line = line.rstrip("\n")
            match = _LOG_RE.match(line)
            if not match:
                continue

            timestamp: str = match.group("timestamp")
            level: str = match.group("level")
            rest: str = match.group("rest")

            if level == "ERROR":
                entries.append(
                    LogEntry(timestamp=timestamp, level=level, message=rest.strip())
                )

            elif level == "WARN":
                entries.append(
                    LogEntry(timestamp=timestamp, level=level, message=rest.strip())
                )

            elif level == "INFO":
                user_match = _USER_RE.match(rest)
                if user_match:
                    user_events.append(
                        UserEvent(
                            timestamp=timestamp,
                            user_id=user_match.group("user_id"),
                            action=user_match.group("action").strip(),
                        )
                    )
                    continue

                api_match = _API_RE.match(rest)
                if api_match:
                    ms = int(api_match.group("ms")) if api_match.group("ms") else 0
                    api_calls.append(
                        ApiCall(
                            timestamp=timestamp,
                            endpoint=api_match.group("endpoint"),
                            ms=ms,
                        )
                    )

    return entries, user_events, api_calls


# ---------------------------------------------------------------------------
# Transform
# ---------------------------------------------------------------------------
def transform(
    log_entries: List[LogEntry],
    user_events: List[UserEvent],
    api_calls: List[ApiCall],
) -> TransformedData:
    """Aggregate parsed records into summary statistics.

    - Errors are counted by message.
    - API latencies are grouped by endpoint.
    - Active sessions are derived from login / logout events.

    Args:
        log_entries: General log entries (ERROR / WARN).
        user_events: User login / logout events.
        api_calls: API call records with latency.

    Returns:
        A ``TransformedData`` instance with aggregated results.
    """
    result = TransformedData()

    # Error summary
    for entry in log_entries:
        if entry.level == "ERROR":
            result.error_summary[entry.message] = (
                result.error_summary.get(entry.message, 0) + 1
            )

    # API latency grouping
    for call in api_calls:
        result.api_latency.setdefault(call.endpoint, []).append(call.ms)

    # Active-session tracking
    for event in user_events:
        if "logged in" in event.action:
            result.active_sessions[event.user_id] = event.timestamp
        elif "logged out" in event.action and event.user_id in result.active_sessions:
            del result.active_sessions[event.user_id]

    return result


# ---------------------------------------------------------------------------
# Load
# ---------------------------------------------------------------------------
def load_to_database(db_path: str, data: TransformedData) -> None:
    """Persist aggregated data to SQLite using parameterized queries.

    Parameterized queries (``?`` placeholders) eliminate the SQL-injection
    risk present in the original string-formatting approach.

    Args:
        db_path: Path to the SQLite database file.
        data: Aggregated data to insert.
    """
    print(f"Connecting to {DB_HOST}:{DB_PORT} as {DB_USER}...")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute(
        "CREATE TABLE IF NOT EXISTS errors (dt TEXT, message TEXT, count INTEGER)"
    )
    cursor.execute(
        "CREATE TABLE IF NOT EXISTS api_metrics (dt TEXT, endpoint TEXT, avg_ms REAL)"
    )

    now = datetime.datetime.now().isoformat()

    for msg, count in data.error_summary.items():
        cursor.execute(
            "INSERT INTO errors VALUES (?, ?, ?)",
            (now, msg, count),
        )

    for endpoint, times in data.api_latency.items():
        avg = sum(times) / len(times)
        cursor.execute(
            "INSERT INTO api_metrics VALUES (?, ?, ?)",
            (now, endpoint, avg),
        )

    conn.commit()
    conn.close()


def generate_report(data: TransformedData, report_path: str) -> None:
    """Render an HTML report from aggregated data.

    The report contains three sections that match the original output:
    error summary, API latency table, and active session count.

    Args:
        data: Aggregated pipeline data.
        report_path: File path for the generated HTML report.
    """
    lines: List[str] = [
        "<html>",
        "<head><title>System Report</title></head>",
        "<body>",
        "<h1>Error Summary</h1>",
        "<ul>",
    ]

    for err_msg, count in data.error_summary.items():
        lines.append(f"<li><b>{err_msg}</b>: {count} occurrences</li>")

    lines.append("</ul>")
    lines.append("<h2>API Latency</h2>")
    lines.append("<table border='1'>")
    lines.append("<tr><th>Endpoint</th><th>Avg (ms)</th></tr>")

    for endpoint, times in data.api_latency.items():
        avg = round(sum(times) / len(times), 1)
        lines.append(f"<tr><td>{endpoint}</td><td>{avg}</td></tr>")

    lines.append("</table>")
    lines.append("<h2>Active Sessions</h2>")
    lines.append(f"<p>{len(data.active_sessions)} user(s) currently active</p>")
    lines.append("</body>")
    lines.append("</html>")

    with open(report_path, "w") as fh:
        fh.write("\n".join(lines) + "\n")


# ---------------------------------------------------------------------------
# Pipeline entry point
# ---------------------------------------------------------------------------
def run_pipeline() -> None:
    """Execute the full Extract → Transform → Load pipeline.

    Reads configuration from environment variables, processes the server
    log, persists results to the database, and writes the HTML report.
    """
    entries, user_events, api_calls = extract_log_entries(LOG_FILE)
    data = transform(entries, user_events, api_calls)
    load_to_database(DB_PATH, data)
    generate_report(data, REPORT_PATH)

    print(f"Job finished at {datetime.datetime.now()}")


def _create_sample_log(log_file: str) -> None:
    """Write a sample ``server.log`` for testing if one does not exist."""
    if os.path.exists(log_file):
        return
    with open(log_file, "w") as fh:
        fh.write("2024-01-01 12:00:00 INFO User 42 logged in\n")
        fh.write("2024-01-01 12:05:00 ERROR Database timeout\n")
        fh.write("2024-01-01 12:05:05 ERROR Database timeout\n")
        fh.write("2024-01-01 12:08:00 INFO API /users/profile took 250ms\n")
        fh.write("2024-01-01 12:09:00 WARN Memory usage at 87%\n")
        fh.write("2024-01-01 12:10:00 INFO User 42 logged out\n")


if __name__ == "__main__":
    _create_sample_log(LOG_FILE)
    run_pipeline()