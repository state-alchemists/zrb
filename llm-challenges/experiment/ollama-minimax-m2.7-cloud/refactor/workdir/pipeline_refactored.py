"""
Pipeline: Server log processing and report generation.

Extracts data from server logs, transforms it into metrics, loads into a SQLite
database, and generates an HTML report.
"""

import datetime
import os
import re
import sqlite3
from typing import TypedDict


# -----------------------------------------------------------------------------
# Configuration (from environment variables)
# -----------------------------------------------------------------------------

DB_PATH: str = os.environ.get("DB_PATH", "metrics.db")
LOG_FILE: str = os.environ.get("LOG_FILE", "server.log")
DB_HOST: str = os.environ.get("DB_HOST", "localhost")
DB_PORT: int = int(os.environ.get("DB_PORT", "5432"))
DB_USER: str = os.environ.get("DB_USER", "admin")
DB_PASS: str = os.environ.get("DB_PASS", "")


# -----------------------------------------------------------------------------
# Type definitions
# -----------------------------------------------------------------------------

class ParsedError(TypedDict):
    """Represents a parsed ERROR log entry."""
    dt: str
    message: str


class ParsedUserEvent(TypedDict):
    """Represents a parsed user session event (login/logout)."""
    dt: str
    uid: str
    action: str


class ParsedApiCall(TypedDict):
    """Represents a parsed API call with latency."""
    dt: str
    endpoint: str
    ms: int


class ParsedLogEntry(TypedDict):
    """Union-like structure for parsed log entries."""
    pass


class AggregatedError(TypedDict):
    """Error message with its occurrence count."""
    message: str
    count: int


class EndpointLatency(TypedDict):
    """Average latency for an endpoint."""
    endpoint: str
    avg_ms: float


# -----------------------------------------------------------------------------
# Extract: Log parsing
# -----------------------------------------------------------------------------

# Regex patterns for structured log parsing
_LOG_TIMESTAMP_RE = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})")
_LOG_LEVEL_RE = re.compile(r"\b(ERROR|INFO|WARN)\b")
_ERROR_MSG_RE = re.compile(r"ERROR (.+)$")
_USER_EVENT_RE = re.compile(r"User (\S+) (logged in|logged out)")
_API_CALL_RE = re.compile(r"API (\S+) took (\d+)ms")


def parse_log_line(line: str) -> dict | None:
    """
    Parse a single log line into a structured record.

    Args:
        line: A single line from the server log.

    Returns:
        A dictionary with keys 'type' and relevant data, or None if unparseable.

    Examples:
        >>> parse_log_line("2024-01-01 12:00:00 INFO User 42 logged in")
        {'type': 'user_event', 'dt': '2024-01-01 12:00:00', 'uid': '42', 'action': 'logged in'}
    """
    timestamp_match = _LOG_TIMESTAMP_RE.match(line)
    if not timestamp_match:
        return None

    dt = timestamp_match.group(1)

    level_match = _LOG_LEVEL_RE.search(line)
    if not level_match:
        return None

    level = level_match.group(1)

    if level == "ERROR":
        error_match = _ERROR_MSG_RE.search(line)
        if error_match:
            return {"type": "error", "dt": dt, "message": error_match.group(1).strip()}

    elif level == "INFO":
        user_match = _USER_EVENT_RE.search(line)
        if user_match:
            return {
                "type": "user_event",
                "dt": dt,
                "uid": user_match.group(1),
                "action": user_match.group(2),
            }

        api_match = _API_CALL_RE.search(line)
        if api_match:
            return {
                "type": "api_call",
                "dt": dt,
                "endpoint": api_match.group(1),
                "ms": int(api_match.group(2)),
            }

    elif level == "WARN":
        # Extract everything after WARN
        warn_content = line[line.find("WARN") + 4:].strip()
        return {"type": "warn", "dt": dt, "message": warn_content}

    return None


def parse_logs(log_path: str) -> tuple[list[ParsedError], list[ParsedApiCall], dict[str, str]]:
    """
    Parse all entries from a server log file.

    Args:
        log_path: Path to the server log file.

    Returns:
        A tuple of (errors, api_calls, active_sessions) where active_sessions
        is a dict mapping user_id to their login timestamp.
    """
    errors: list[ParsedError] = []
    api_calls: list[ParsedApiCall] = []
    active_sessions: dict[str, str] = {}

    if not os.path.exists(log_path):
        return errors, api_calls, active_sessions

    with open(log_path, "r") as f:
        for line in f:
            parsed = parse_log_line(line)
            if parsed is None:
                continue

            match parsed["type"]:
                case "error":
                    errors.append({"dt": parsed["dt"], "message": parsed["message"]})
                case "api_call":
                    api_calls.append({
                        "dt": parsed["dt"],
                        "endpoint": parsed["endpoint"],
                        "ms": parsed["ms"],
                    })
                case "user_event":
                    uid = parsed["uid"]
                    action = parsed["action"]
                    if action == "logged in":
                        active_sessions[uid] = parsed["dt"]
                    elif action == "logged out" and uid in active_sessions:
                        del active_sessions[uid]

    return errors, api_calls, active_sessions


# -----------------------------------------------------------------------------
# Transform: Data aggregation
# -----------------------------------------------------------------------------

def aggregate_errors(errors: list[ParsedError]) -> list[AggregatedError]:
    """
    Count occurrences of each unique error message.

    Args:
        errors: List of parsed error records.

    Returns:
        List of aggregated errors with message and count, sorted by count descending.
    """
    counts: dict[str, int] = {}
    for err in errors:
        msg = err["message"]
        counts[msg] = counts.get(msg, 0) + 1

    return [{"message": msg, "count": count} for msg, count in counts.items()]


def compute_api_latency(api_calls: list[ParsedApiCall]) -> list[EndpointLatency]:
    """
    Compute average latency per API endpoint.

    Args:
        api_calls: List of parsed API call records.

    Returns:
        List of endpoint latency records, sorted by endpoint name.
    """
    by_endpoint: dict[str, list[int]] = {}
    for call in api_calls:
        ep = call["endpoint"]
        by_endpoint.setdefault(ep, []).append(call["ms"])

    result = [
        {"endpoint": ep, "avg_ms": sum(times) / len(times)}
        for ep, times in by_endpoint.items()
    ]
    result.sort(key=lambda x: x["endpoint"])
    return result


# -----------------------------------------------------------------------------
# Load: Database and report generation
# -----------------------------------------------------------------------------

def init_database(conn: sqlite3.Connection) -> None:
    """
    Create required tables if they don't exist.

    Args:
        conn: Active SQLite connection.
    """
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS errors (
            dt TEXT,
            message TEXT,
            count INTEGER
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS api_metrics (
            dt TEXT,
            endpoint TEXT,
            avg_ms REAL
        )
        """
    )


def store_errors(conn: sqlite3.Connection, aggregated: list[AggregatedError]) -> None:
    """
    Insert aggregated error counts into the database using parameterized queries.

    Args:
        conn: Active SQLite connection.
        aggregated: List of aggregated error records.
    """
    cursor = conn.cursor()
    now = datetime.datetime.now().isoformat()
    for err in aggregated:
        cursor.execute(
            "INSERT INTO errors (dt, message, count) VALUES (?, ?, ?)",
            (now, err["message"], err["count"]),
        )


def store_api_metrics(conn: sqlite3.Connection, latency: list[EndpointLatency]) -> None:
    """
    Insert API latency averages into the database using parameterized queries.

    Args:
        conn: Active SQLite connection.
        latency: List of endpoint latency records.
    """
    cursor = conn.cursor()
    now = datetime.datetime.now().isoformat()
    for record in latency:
        cursor.execute(
            "INSERT INTO api_metrics (dt, endpoint, avg_ms) VALUES (?, ?, ?)",
            (now, record["endpoint"], record["avg_ms"]),
        )


def build_html_report(
    errors: list[AggregatedError],
    latency: list[EndpointLatency],
    active_sessions: int,
) -> str:
    """
    Generate the HTML report string from processed data.

    Args:
        errors: Aggregated error list.
        latency: API endpoint latency list.
        active_sessions: Number of currently active user sessions.

    Returns:
        Complete HTML document as a string.
    """
    lines: list[str] = [
        "<html>",
        "<head><title>System Report</title></head>",
        "<body>",
        "<h1>Error Summary</h1>",
        "<ul>",
    ]

    for err in errors:
        lines.append(f"<li><b>{err['message']}</b>: {err['count']} occurrences</li>")

    lines.extend([
        "</ul>",
        "<h2>API Latency</h2>",
        "<table border='1'>",
        "<tr><th>Endpoint</th><th>Avg (ms)</th></tr>",
    ])

    for record in latency:
        lines.append(
            f"<tr><td>{record['endpoint']}</td>"
            f"<td>{round(record['avg_ms'], 1)}</td></tr>"
        )

    lines.extend([
        "</table>",
        "<h2>Active Sessions</h2>",
        f"<p>{active_sessions} user(s) currently active</p>",
        "</body>",
        "</html>",
    ])

    return "\n".join(lines)


def generate_report(
    errors: list[AggregatedError],
    latency: list[EndpointLatency],
    active_sessions: int,
    output_path: str,
) -> None:
    """
    Generate and write the HTML report to a file.

    Args:
        errors: Aggregated error list.
        latency: API endpoint latency list.
        active_sessions: Number of currently active user sessions.
        output_path: Destination file path for the HTML report.
    """
    html = build_html_report(errors, latency, active_sessions)
    with open(output_path, "w") as f:
        f.write(html)


# -----------------------------------------------------------------------------
# Main pipeline
# -----------------------------------------------------------------------------

def run_pipeline() -> None:
    """
    Execute the full ETL pipeline: extract, transform, load, and report.

    Reads the log file configured via environment variables, processes entries,
    stores metrics in SQLite, and writes an HTML report.
    """
    print(f"Connecting to {DB_HOST}:{DB_PORT} as {DB_USER}...")

    # Extract
    errors, api_calls, active_sessions = parse_logs(LOG_FILE)
    session_count = len(active_sessions)

    # Transform
    aggregated_errors = aggregate_errors(errors)
    endpoint_latency = compute_api_latency(api_calls)

    # Load — database
    conn = sqlite3.connect(DB_PATH)
    try:
        init_database(conn)
        store_errors(conn, aggregated_errors)
        store_api_metrics(conn, endpoint_latency)
        conn.commit()
    finally:
        conn.close()

    # Load — report
    generate_report(aggregated_errors, endpoint_latency, session_count, "report.html")

    print(f"Job finished at {datetime.datetime.now()}")


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