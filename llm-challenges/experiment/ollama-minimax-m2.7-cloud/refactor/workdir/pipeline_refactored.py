"""
Server log processing pipeline.

Extracts metrics from server logs, stores them in SQLite, and generates an HTML report.
"""

import datetime
import os
import re
import sqlite3
from typing import TypedDict


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

class ErrorRecord(TypedDict):
    dt: str
    message: str


class SessionRecord(TypedDict):
    uid: str
    action: str


class ApiCallRecord(TypedDict):
    dt: str
    endpoint: str
    ms: int


# ---------------------------------------------------------------------------
# Configuration (from environment)
# ---------------------------------------------------------------------------

DB_PATH: str = os.environ.get("DB_PATH", "metrics.db")
LOG_FILE: str = os.environ.get("LOG_FILE", "server.log")
DB_HOST: str = os.environ.get("DB_HOST", "localhost")
DB_PORT: int = int(os.environ.get("DB_PORT", "5432"))
DB_USER: str = os.environ.get("DB_USER", "admin")
DB_PASS: str = os.environ.get("DB_PASS", "")


# ---------------------------------------------------------------------------
# Regex patterns for log parsing
# ---------------------------------------------------------------------------

# Format: 2024-01-01 12:00:00 LEVEL Message
LOG_PATTERN = re.compile(
    r"^(?P<date>\d{4}-\d{2}-\d{2})\s+(?P<time>\d{2}:\d{2}:\d{2})\s+"
    r"(?P<level>ERROR|WARN|INFO)\s+(?P<message>.*)$"
)

# User action: User <id> <action text>
USER_ACTION_PATTERN = re.compile(r"User\s+(?P<uid>\S+)\s+(?P<action>.+)$")

# API call: API /endpoint took Nms
API_CALL_PATTERN = re.compile(r"API\s+(?P<endpoint>\S+)\s+took\s+(?P<ms>\d+)ms")


# ---------------------------------------------------------------------------
# Extract
# ---------------------------------------------------------------------------

def extract_log_data(log_path: str) -> tuple[list[ErrorRecord], dict[str, str], list[ApiCallRecord]]:
    """
    Read the log file and extract structured records.

    Returns:
        Tuple of (error_records, active_sessions, api_calls).
        active_sessions is a dict mapping user ID to login timestamp.
    """
    errors: list[ErrorRecord] = []
    sessions: dict[str, str] = {}
    api_calls: list[ApiCallRecord] = []

    if not os.path.exists(log_path):
        print(f"Log file not found: {log_path}")
        return errors, sessions, api_calls

    with open(log_path, "r") as f:
        for line in f:
            match = LOG_PATTERN.match(line)
            if not match:
                continue

            dt = f"{match['date']} {match['time']}"
            level = match["level"]
            message = match["message"].strip()

            if level == "ERROR":
                errors.append({"dt": dt, "message": message})

            elif level == "WARN":
                # Warnings are logged but not aggregated in the report
                pass

            elif level == "INFO":
                user_match = USER_ACTION_PATTERN.search(message)
                if user_match:
                    uid = user_match["uid"]
                    action = user_match["action"]
                    if "logged in" in action:
                        sessions[uid] = dt
                    elif "logged out" in action and uid in sessions:
                        del sessions[uid]

                api_match = API_CALL_PATTERN.search(message)
                if api_match:
                    api_calls.append({
                        "dt": dt,
                        "endpoint": api_match["endpoint"],
                        "ms": int(api_match["ms"]),
                    })

    return errors, sessions, api_calls


# ---------------------------------------------------------------------------
# Transform
# ---------------------------------------------------------------------------

def transform_errors(errors: list[ErrorRecord]) -> dict[str, int]:
    """
    Aggregate error messages by text, counting occurrences.

    Returns:
        Dict mapping error message to occurrence count.
    """
    counts: dict[str, int] = {}
    for err in errors:
        msg = err["message"]
        counts[msg] = counts.get(msg, 0) + 1
    return counts


def transform_api_metrics(api_calls: list[ApiCallRecord]) -> dict[str, list[int]]:
    """
    Group API call durations by endpoint.

    Returns:
        Dict mapping endpoint path to list of response times in ms.
    """
    stats: dict[str, list[int]] = {}
    for call in api_calls:
        stats.setdefault(call["endpoint"], []).append(call["ms"])
    return stats


# ---------------------------------------------------------------------------
# Load
# ---------------------------------------------------------------------------

def load_to_database(
    db_path: str,
    error_counts: dict[str, int],
    endpoint_stats: dict[str, list[int]],
) -> None:
    """
    Write aggregated metrics into the SQLite database using parameterized queries.
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

    for msg, count in error_counts.items():
        cursor.execute(
            "INSERT INTO errors VALUES (?, ?, ?)",
            (now, msg, count),
        )

    for endpoint, times in endpoint_stats.items():
        avg = sum(times) / len(times)
        cursor.execute(
            "INSERT INTO api_metrics VALUES (?, ?, ?)",
            (now, endpoint, avg),
        )

    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Report Generation
# ---------------------------------------------------------------------------

def generate_report(
    output_path: str,
    error_counts: dict[str, int],
    endpoint_stats: dict[str, list[int]],
    active_session_count: int,
) -> None:
    """
    Write the HTML report to disk.

    Includes: error summary, API latency table, active session count.
    """
    lines: list[str] = [
        "<html>",
        "<head><title>System Report</title></head>",
        "<body>",
        "<h1>Error Summary</h1>",
        "<ul>",
    ]

    for err_msg, count in error_counts.items():
        lines.append(f"<li><b>{err_msg}</b>: {count} occurrences</li>")

    lines.extend([
        "</ul>",
        "<h2>API Latency</h2>",
        "<table border='1'>",
        "<tr><th>Endpoint</th><th>Avg (ms)</th></tr>",
    ])

    for endpoint, times in endpoint_stats.items():
        avg = sum(times) / len(times)
        lines.append(f"<tr><td>{endpoint}</td><td>{round(avg, 1)}</td></tr>")

    lines.extend([
        "</table>",
        "<h2>Active Sessions</h2>",
        f"<p>{active_session_count} user(s) currently active</p>",
        "</body>",
        "</html>",
    ])

    with open(output_path, "w") as f:
        f.write("\n".join(lines))


# ---------------------------------------------------------------------------
# Main Pipeline
# ---------------------------------------------------------------------------

def run_pipeline() -> None:
    """Execute the full ETL pipeline: extract → transform → load → report."""
    # Extract
    errors, sessions, api_calls = extract_log_data(LOG_FILE)

    # Transform
    error_counts = transform_errors(errors)
    endpoint_stats = transform_api_metrics(api_calls)

    # Load
    load_to_database(DB_PATH, error_counts, endpoint_stats)

    # Report
    generate_report("report.html", error_counts, endpoint_stats, len(sessions))

    print(f"Job finished at {datetime.datetime.now()}")


if __name__ == "__main__":
    # Create sample log if it doesn't exist (for development/demo)
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