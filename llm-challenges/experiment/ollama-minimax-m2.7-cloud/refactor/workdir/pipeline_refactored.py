"""
Server log processing pipeline.

Extracts data from server logs, transforms it, loads into SQLite,
and generates an HTML report.
"""

import datetime
import os
import re
import sqlite3
from typing import TypedDict

# ============================================================================
# Configuration (from environment variables with sensible defaults for dev)
# ============================================================================

DB_PATH: str = os.environ.get("DB_PATH", "metrics.db")
LOG_FILE: str = os.environ.get("LOG_FILE", "server.log")
DB_HOST: str = os.environ.get("DB_HOST", "localhost")
DB_PORT: int = int(os.environ.get("DB_PORT", "5432"))
DB_USER: str = os.environ.get("DB_USER", "")
DB_PASS: str = os.environ.get("DB_PASS", "")
REPORT_PATH: str = os.environ.get("REPORT_PATH", "report.html")


# ============================================================================
# Data Structures
# ============================================================================

class ErrorEntry(TypedDict):
    dt: str
    t: str
    m: str


class UserActionEntry(TypedDict):
    dt: str
    t: str
    u: str
    a: str


class WarnEntry(TypedDict):
    dt: str
    t: str
    m: str


class APICall(TypedDict):
    dt: str
    endpoint: str
    ms: int


LogEntry = ErrorEntry | UserActionEntry | WarnEntry


# ============================================================================
# Regex Patterns
# ============================================================================

# Log format: 2024-01-01 12:00:00 LEVEL Message
LOG_PATTERN = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) "
    r"(?P<level>ERROR|INFO|WARN) "
    r"(?P<message>.*)$"
)

# User action: User <uid> <action>
USER_PATTERN = re.compile(r"^User (?P<uid>\S+) (?P<action>.*)$")

# API call: API <endpoint> took <duration>ms
API_PATTERN = re.compile(r"^API (?P<endpoint>\S+) took (?P<ms>\d+)ms$")


# ============================================================================
# Extract Phase
# ============================================================================

def read_log_lines(log_path: str) -> list[str]:
    """
    Read all lines from the log file.

    Args:
        log_path: Path to the server log file.

    Returns:
        List of log lines, or empty list if file doesn't exist.
    """
    if not os.path.exists(log_path):
        return []
    with open(log_path, "r") as f:
        return f.readlines()


def parse_log_line(line: str) -> LogEntry | APICall | None:
    """
    Parse a single log line into a structured record.

    Args:
        line: A single line from the server log.

    Returns:
        A TypedDict record for the appropriate log type, or None if unparseable.
    """
    match = LOG_PATTERN.match(line)
    if not match:
        return None

    timestamp = match.group("timestamp")
    level = match.group("level")
    message = match.group("message")

    if level == "ERROR":
        return ErrorEntry(dt=timestamp, t="ERR", m=message)

    if level == "WARN":
        return WarnEntry(dt=timestamp, t="WARN", m=message)

    if level == "INFO":
        user_match = USER_PATTERN.match(message)
        if user_match:
            uid = user_match.group("uid")
            action = user_match.group("action")
            return UserActionEntry(dt=timestamp, t="USR", u=uid, a=action)

        api_match = API_PATTERN.match(message)
        if api_match:
            return APICall(
                dt=timestamp,
                endpoint=api_match.group("endpoint"),
                ms=int(api_match.group("ms")),
            )

    return None


def extract_all_entries(log_lines: list[str]) -> tuple[list[LogEntry], list[APICall]]:
    """
    Parse all log lines into separate collections.

    Args:
        log_lines: Raw lines from the log file.

    Returns:
        Tuple of (general_log_entries, api_calls).
    """
    log_entries: list[LogEntry] = []
    api_calls: list[APICall] = []

    for line in log_lines:
        parsed = parse_log_line(line)
        if parsed is None:
            continue
        if isinstance(parsed, dict) and "endpoint" in parsed:
            api_calls.append(parsed)  # type: ignore[arg-type]
        elif isinstance(parsed, dict):
            log_entries.append(parsed)  # type: ignore[arg-type]

    return log_entries, api_calls


# ============================================================================
# Transform Phase
# ============================================================================

def build_error_summary(log_entries: list[LogEntry]) -> dict[str, int]:
    """
    Count occurrences of each unique error message.

    Args:
        log_entries: Parsed log entries containing errors.

    Returns:
        Dictionary mapping error message to occurrence count.
    """
    summary: dict[str, int] = {}
    for entry in log_entries:
        if entry["t"] == "ERR":
            msg = entry["m"]
            summary[msg] = summary.get(msg, 0) + 1
    return summary


def build_api_stats(api_calls: list[APICall]) -> dict[str, list[int]]:
    """
    Group API calls by endpoint and collect their durations.

    Args:
        api_calls: Parsed API call records.

    Returns:
        Dictionary mapping endpoint to list of duration measurements (ms).
    """
    stats: dict[str, list[int]] = {}
    for call in api_calls:
        stats.setdefault(call["endpoint"], []).append(call["ms"])
    return stats


def compute_avg_latency(api_stats: dict[str, list[int]]) -> dict[str, float]:
    """
    Compute average latency per endpoint.

    Args:
        api_stats: Endpoint to duration list mapping.

    Returns:
        Dictionary mapping endpoint to average latency in ms.
    """
    return {ep: sum(times) / len(times) for ep, times in api_stats.items()}


def track_sessions(log_entries: list[LogEntry]) -> dict[str, str]:
    """
    Track active user sessions based on login/logout events.

    Args:
        log_entries: Parsed log entries containing user actions.

    Returns:
        Dictionary mapping user ID to login timestamp.
    """
    sessions: dict[str, str] = {}
    for entry in log_entries:
        if entry["t"] != "USR":
            continue
        uid = entry["u"]
        action = entry["a"]
        if "logged in" in action:
            sessions[uid] = entry["dt"]
        elif "logged out" in action and uid in sessions:
            del sessions[uid]
    return sessions


# ============================================================================
# Load Phase
# ============================================================================

def init_db(db_path: str) -> sqlite3.Connection:
    """
    Initialize the SQLite database with required tables.

    Args:
        db_path: Path to the SQLite database file.

    Returns:
        Active database connection.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        "CREATE TABLE IF NOT EXISTS errors (dt TEXT, message TEXT, count INTEGER)"
    )
    cursor.execute(
        "CREATE TABLE IF NOT EXISTS api_metrics (dt TEXT, endpoint TEXT, avg_ms REAL)"
    )
    return conn


def load_error_summary(
    conn: sqlite3.Connection, summary: dict[str, int], timestamp: str
) -> None:
    """
    Insert error summary into the database.

    Args:
        conn: Active database connection.
        summary: Error message to count mapping.
        timestamp: Datetime string to record.
    """
    cursor = conn.cursor()
    for msg, count in summary.items():
        # Parameterized query — safe from injection
        cursor.execute(
            "INSERT INTO errors (dt, message, count) VALUES (?, ?, ?)",
            (timestamp, msg, count),
        )


def load_api_metrics(
    conn: sqlite3.Connection, avg_latency: dict[str, float], timestamp: str
) -> None:
    """
    Insert API latency metrics into the database.

    Args:
        conn: Active database connection.
        avg_latency: Endpoint to average latency mapping.
        timestamp: Datetime string to record.
    """
    cursor = conn.cursor()
    for ep, avg in avg_latency.items():
        # Parameterized query — safe from injection
        cursor.execute(
            "INSERT INTO api_metrics (dt, endpoint, avg_ms) VALUES (?, ?, ?)",
            (timestamp, ep, avg),
        )


def generate_html_report(
    error_summary: dict[str, int],
    avg_latency: dict[str, float],
    active_sessions: int,
    output_path: str,
) -> None:
    """
    Generate the HTML report file.

    Args:
        error_summary: Error message to count mapping.
        avg_latency: Endpoint to average latency mapping.
        active_sessions: Number of currently active sessions.
        output_path: Destination file path for the report.
    """
    lines: list[str] = [
        "<html>",
        "<head><title>System Report</title></head>",
        "<body>",
        "<h1>Error Summary</h1>",
        "<ul>",
    ]

    for err_msg, count in error_summary.items():
        lines.append(f"<li><b>{err_msg}</b>: {count} occurrences</li>")

    lines.extend([
        "</ul>",
        "<h2>API Latency</h2>",
        "<table border='1'>",
        "<tr><th>Endpoint</th><th>Avg (ms)</th></tr>",
    ])

    for ep, avg in avg_latency.items():
        lines.append(f"<tr><td>{ep}</td><td>{round(avg, 1)}</td></tr>")

    lines.extend([
        "</table>",
        "<h2>Active Sessions</h2>",
        f"<p>{active_sessions} user(s) currently active</p>",
        "</body>",
        "</html>",
    ])

    with open(output_path, "w") as f:
        f.write("\n".join(lines))


# ============================================================================
# Main Pipeline
# ============================================================================

def run_pipeline() -> None:
    """
    Execute the full ETL pipeline: extract → transform → load → report.
    """
    # Configuration
    log_path = LOG_FILE
    db_path = DB_PATH
    report_path = REPORT_PATH

    # Extract
    log_lines = read_log_lines(log_path)
    log_entries, api_calls = extract_all_entries(log_lines)

    # Transform
    error_summary = build_error_summary(log_entries)
    api_stats = build_api_stats(api_calls)
    avg_latency = compute_avg_latency(api_stats)
    active_sessions = track_sessions(log_entries)

    # Load
    timestamp = datetime.datetime.now().isoformat()
    conn = init_db(db_path)
    try:
        load_error_summary(conn, error_summary, timestamp)
        load_api_metrics(conn, avg_latency, timestamp)
        conn.commit()
    finally:
        conn.close()

    # Report
    generate_html_report(error_summary, avg_latency, len(active_sessions), report_path)

    print(f"Job finished at {timestamp}")


if __name__ == "__main__":
    # Create sample log for testing if it doesn't exist
    if not os.path.exists(LOG_FILE):
        sample_lines = [
            "2024-01-01 12:00:00 INFO User 42 logged in",
            "2024-01-01 12:05:00 ERROR Database timeout",
            "2024-01-01 12:05:05 ERROR Database timeout",
            "2024-01-01 12:08:00 INFO API /users/profile took 250ms",
            "2024-01-01 12:09:00 WARN Memory usage at 87%",
            "2024-01-01 12:10:00 INFO User 42 logged out",
        ]
        with open(LOG_FILE, "w") as f:
            f.write("\n".join(sample_lines) + "\n")

    run_pipeline()
