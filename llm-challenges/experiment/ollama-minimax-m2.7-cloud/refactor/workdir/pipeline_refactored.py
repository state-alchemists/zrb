"""
Server log processing pipeline.

Extracts structured data from server logs, aggregates metrics, stores them in a
SQLite database, and generates an HTML report.

Environment variables:
    DB_PATH          Path to SQLite database (default: metrics.db)
    LOG_FILE         Path to server log file (default: server.log)
    DB_HOST          Database host (default: localhost)
    DB_PORT          Database port (default: 5432)
    DB_USER          Database username (default: admin)
    DB_PASS          Database password (default: password123)
"""

import datetime
import os
import re
import sqlite3
from typing import TypedDict


# --- Typedefs for structured data -------------------------------------------

class ErrorEntry(TypedDict):
    """Error log entry."""
    dt: str
    msg: str


class UserSession(TypedDict):
    """User session record."""
    uid: str
    action: str


class ApiCall(TypedDict):
    """API latency record."""
    dt: str
    endpoint: str
    ms: int


class ParsedLogData(TypedDict):
    """Aggregated parsed log data."""
    errors: list[ErrorEntry]
    sessions: dict[str, str]
    api_calls: list[ApiCall]


# --- Configuration -----------------------------------------------------------

def _get_config() -> dict[str, str]:
    """Load configuration from environment variables with safe defaults."""
    return {
        "db_path": os.environ.get("DB_PATH", "metrics.db"),
        "log_file": os.environ.get("LOG_FILE", "server.log"),
        "db_host": os.environ.get("DB_HOST", "localhost"),
        "db_port": os.environ.get("DB_PORT", "5432"),
        "db_user": os.environ.get("DB_USER", "admin"),
        "db_pass": os.environ.get("DB_PASS", "password123"),
    }


# --- EXTRACT: Parse log file -------------------------------------------------

LOG_PATTERN = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) "
    r"(?P<level>ERROR|INFO|WARN)\s+"
    r"(?P<body>.*)$"
)

USER_PATTERN = re.compile(r"User (?P<uid>\S+) (?P<action>.*)")
API_PATTERN = re.compile(r"API (?P<endpoint>\S+) took (?P<ms>\d+)ms")


def extract_log_entries(log_path: str) -> list[dict]:
    """
    Read and extract raw entries from a server log file.

    Args:
        log_path: Path to the server log file.

    Yields:
        Dictionaries with keys: dt, level, body.
    """
    if not os.path.exists(log_path):
        return []

    with open(log_path, "r") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            match = LOG_PATTERN.match(line)
            if match:
                yield {
                    "dt": match.group("timestamp"),
                    "level": match.group("level"),
                    "body": match.group("body"),
                }


def extract(log_path: str) -> ParsedLogData:
    """
    Extract and classify structured data from a server log.

    Args:
        log_path: Path to the server log file.

    Returns:
        ParsedLogData containing errors, sessions, and API call records.
    """
    data: ParsedLogData = {"errors": [], "sessions": {}, "api_calls": []}

    for entry in extract_log_entries(log_path):
        dt = entry["dt"]
        level = entry["level"]
        body = entry["body"]

        if level == "ERROR":
            data["errors"].append({"dt": dt, "msg": body})

        elif level == "INFO":
            user_match = USER_PATTERN.match(body)
            if user_match:
                uid = user_match.group("uid")
                action = user_match.group("action")
                data["sessions"][uid] = dt  # keyed by uid for active tracking

            api_match = API_PATTERN.match(body)
            if api_match:
                data["api_calls"].append({
                    "dt": dt,
                    "endpoint": api_match.group("endpoint"),
                    "ms": int(api_match.group("ms")),
                })

    return data


# --- TRANSFORM: Aggregate raw data ------------------------------------------

def transform(data: ParsedLogData) -> tuple[dict[str, int], dict[str, list[int]], int]:
    """
    Compute aggregated metrics from parsed log data.

    Args:
        data: Parsed log data from extract().

    Returns:
        Tuple of (error_counts, endpoint_latencies, active_session_count).
    """
    # Count identical error messages
    error_counts: dict[str, int] = {}
    for err in data["errors"]:
        msg = err["msg"]
        error_counts[msg] = error_counts.get(msg, 0) + 1

    # Group API latencies by endpoint
    endpoint_latencies: dict[str, list[int]] = {}
    for call in data["api_calls"]:
        ep = call["endpoint"]
        endpoint_latencies.setdefault(ep, []).append(call["ms"])

    active_session_count = len(data["sessions"])

    return error_counts, endpoint_latencies, active_session_count


# --- LOAD: Persist to DB and generate report --------------------------------

def _init_db(conn: sqlite3.Connection) -> None:
    """Create tables if they don't exist."""
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS errors (
            dt TEXT,
            message TEXT,
            count INTEGER
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS api_metrics (
            dt TEXT,
            endpoint TEXT,
            avg_ms REAL
        )
    """)
    conn.commit()


def load(
    conn: sqlite3.Connection,
    error_counts: dict[str, int],
    endpoint_latencies: dict[str, list[int]],
    active_session_count: int,
) -> None:
    """
    Persist aggregated metrics to the database.

    Args:
        conn: SQLite database connection.
        error_counts: Error message -> occurrence count mapping.
        endpoint_latencies: Endpoint -> list of latency values mapping.
        active_session_count: Number of currently active sessions.
    """
    _init_db(conn)
    cursor = conn.cursor()
    now = datetime.datetime.now().isoformat()

    # Insert error counts using parameterized queries
    for msg, count in error_counts.items():
        cursor.execute(
            "INSERT INTO errors (dt, message, count) VALUES (?, ?, ?)",
            (now, msg, count),
        )

    # Insert API latency averages using parameterized queries
    for ep, times in endpoint_latencies.items():
        avg_ms = sum(times) / len(times)
        cursor.execute(
            "INSERT INTO api_metrics (dt, endpoint, avg_ms) VALUES (?, ?, ?)",
            (now, ep, avg_ms),
        )

    conn.commit()


def generate_report(
    error_counts: dict[str, int],
    endpoint_latencies: dict[str, list[int]],
    active_session_count: int,
    output_path: str,
) -> None:
    """
    Write the HTML report to disk.

    Args:
        error_counts: Error message -> occurrence count mapping.
        endpoint_latencies: Endpoint -> list of latency values mapping.
        active_session_count: Number of currently active sessions.
        output_path: Destination file path for the HTML report.
    """
    lines = [
        "<html>",
        "<head><title>System Report</title></head>",
        "<body>",
        "<h1>Error Summary</h1>",
        "<ul>",
    ]

    for msg, count in error_counts.items():
        lines.append(f"<li><b>{msg}</b>: {count} occurrences</li>")

    lines.append("</ul>")
    lines.append("<h2>API Latency</h2>")
    lines.append("<table border='1'>")
    lines.append("<tr><th>Endpoint</th><th>Avg (ms)</th></tr>")

    for ep, times in endpoint_latencies.items():
        avg = sum(times) / len(times)
        lines.append(f"<tr><td>{ep}</td><td>{round(avg, 1)}</td></tr>")

    lines.append("</table>")
    lines.append("<h2>Active Sessions</h2>")
    lines.append(f"<p>{active_session_count} user(s) currently active</p>")
    lines.append("</body>")
    lines.append("</html>")

    with open(output_path, "w") as fh:
        fh.write("\n".join(lines))


# --- Pipeline orchestration -------------------------------------------------

def run_pipeline() -> None:
    """Execute the full Extract → Transform → Load pipeline."""
    config = _get_config()

    print(
        f"Connecting to {config['db_host']}:{config['db_port']} "
        f"as {config['db_user']}..."
    )

    # Extract
    data = extract(config["log_file"])

    # Transform
    error_counts, endpoint_latencies, active_session_count = transform(data)

    # Load
    conn = sqlite3.connect(config["db_path"])
    try:
        load(conn, error_counts, endpoint_latencies, active_session_count)
    finally:
        conn.close()

    # Generate report
    generate_report(
        error_counts,
        endpoint_latencies,
        active_session_count,
        "report.html",
    )

    print(f"Job finished at {datetime.datetime.now()}")


# --- Bootstrap --------------------------------------------------------------

if __name__ == "__main__":
    # Create a sample log for testing if none exists
    log_file = os.environ.get("LOG_FILE", "server.log")
    if not os.path.exists(log_file):
        sample_log = (
            "2024-01-01 12:00:00 INFO User 42 logged in\n"
            "2024-01-01 12:05:00 ERROR Database timeout\n"
            "2024-01-01 12:05:05 ERROR Database timeout\n"
            "2024-01-01 12:08:00 INFO API /users/profile took 250ms\n"
            "2024-01-01 12:09:00 WARN Memory usage at 87%\n"
            "2024-01-01 12:10:00 INFO User 42 logged out\n"
        )
        with open(log_file, "w") as fh:
            fh.write(sample_log)

    run_pipeline()
