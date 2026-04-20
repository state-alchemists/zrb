"""
Pipeline script for processing server logs and generating a report.
Follows ETL (Extract, Transform, Load) pattern.

Environment Variables:
    LOG_FILE: Path to the server log file (default: server.log)
    DB_PATH: Path to the SQLite database file (default: metrics.db)
    REPORT_PATH: Path to the output HTML report (default: report.html)
"""

import datetime
import os
import re
import sqlite3
from typing import Optional

# Configuration via environment variables
LOG_FILE = os.getenv("LOG_FILE", "server.log")
DB_PATH = os.getenv("DB_PATH", "metrics.db")
REPORT_PATH = os.getenv("REPORT_PATH", "report.html")

# Regex pattern for parsing log lines
# Expected format: YYYY-MM-DD HH:MM:SS LEVEL [message details]
LOG_LINE_PATTERN = re.compile(
    r"^(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\s+(INFO|ERROR|WARN)\s+(.*)$"
)

# Pattern for extracting user info from log lines
USER_PATTERN = re.compile(r"User\s+(\d+)\s+(.+)$")

# Pattern for extracting API metrics from log lines
API_PATTERN = re.compile(r"API\s+(\S+)\s+took\s+(\d+)\s*ms")


def parse_log_line(line: str) -> Optional[dict]:
    """
    Parse a single log line using regex.

    Returns a dict with keys: datetime, level, message, or None if parsing fails.
    """
    match = LOG_LINE_PATTERN.match(line.strip())
    if not match:
        return None

    datetime_str, level, message = match.groups()
    return {
        "datetime": datetime_str,
        "level": level,
        "message": message,
    }


def extract_user_info(message: str) -> Optional[dict]:
    """
    Extract user ID and action from a log message.
    Returns dict with 'user_id' and 'action', or None if not a user event.
    """
    match = USER_PATTERN.search(message)
    if not match:
        return None

    user_id, action = match.groups()
    return {"user_id": user_id, "action": action}


def extract_api_metrics(message: str) -> Optional[dict]:
    """
    Extract API endpoint and duration from a log message.
    Returns dict with 'endpoint' and 'duration_ms', or None if not an API event.
    """
    match = API_PATTERN.search(message)
    if not match:
        return None

    endpoint, duration = match.groups()
    return {"endpoint": endpoint, "duration_ms": int(duration)}


def extract_logs(log_file: str) -> tuple[list[dict], dict[str, str], list[dict], list[dict]]:
    """
    Extract data from log file.

    Returns:
        error_entries: List of ERROR level entries for error summary
        sessions: Dict of active user sessions {user_id: timestamp}
        api_calls: List of API call metrics
        all_entries: List of all parsed entries (for backward compatibility)
    """
    error_entries = []
    sessions = {}
    api_calls = []

    if not os.path.exists(log_file):
        return error_entries, sessions, api_calls, []

    with open(log_file, "r") as f:
        for line in f:
            parsed = parse_log_line(line)
            if parsed is None:
                continue

            level = parsed["level"]

            if level == "ERROR":
                error_entries.append(
                    {
                        "datetime": parsed["datetime"],
                        "message": parsed["message"],
                    }
                )

            elif level == "INFO":
                user_info = extract_user_info(parsed["message"])
                if user_info:
                    uid = user_info["user_id"]
                    action = user_info["action"]
                    if "logged in" in action:
                        sessions[uid] = parsed["datetime"]
                    elif "logged out" in action and uid in sessions:
                        sessions.pop(uid)

                api_metrics = extract_api_metrics(parsed["message"])
                if api_metrics:
                    api_calls.append(
                        {
                            "datetime": parsed["datetime"],
                            "endpoint": api_metrics["endpoint"],
                            "duration_ms": api_metrics["duration_ms"],
                        }
                    )

            elif level == "WARN":
                # WARN entries are not included in error summary
                pass

    return error_entries, sessions, api_calls, []


def transform_error_summary(errors: list[dict]) -> dict[str, int]:
    """
    Transform error list into a summary count by message.
    All entries in errors list are ERROR level entries.
    """
    summary = {}
    for err in errors:
        msg = err.get("message", "")
        summary[msg] = summary.get(msg, 0) + 1
    return summary


def transform_api_metrics(api_calls: list[dict]) -> dict[str, list[int]]:
    """
    Transform API calls into per-endpoint metrics for averaging.
    """
    endpoint_stats: dict[str, list[int]] = {}
    for call in api_calls:
        ep = call["endpoint"]
        endpoint_stats.setdefault(ep, []).append(call["duration_ms"])
    return endpoint_stats


def load_to_db(db_path: str, errors: list[dict], api_calls: list[dict]) -> None:
    """
    Load processed data into SQLite database using parameterized queries.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create tables if not exist
    cursor.execute(
        "CREATE TABLE IF NOT EXISTS errors (timestamp TEXT, message TEXT, count INTEGER)"
    )
    cursor.execute(
        "CREATE TABLE IF NOT EXISTS api_metrics (timestamp TEXT, endpoint TEXT, avg_ms REAL)"
    )

    # Insert error summary using parameterized queries
    timestamp = datetime.datetime.now().isoformat()
    error_summary = transform_error_summary(errors)
    for msg, count in error_summary.items():
        cursor.execute(
            "INSERT INTO errors (timestamp, message, count) VALUES (?, ?, ?)",
            (timestamp, msg, count),
        )

    # Insert API metrics using parameterized queries
    endpoint_stats = transform_api_metrics(api_calls)
    for endpoint, times in endpoint_stats.items():
        avg_ms = sum(times) / len(times)
        cursor.execute(
            "INSERT INTO api_metrics (timestamp, endpoint, avg_ms) VALUES (?, ?, ?)",
            (timestamp, endpoint, avg_ms),
        )

    conn.commit()
    conn.close()


def generate_report(
    errors: list[dict], api_calls: list[dict], sessions: dict[str, str]
) -> str:
    """
    Generate HTML report content.
    """
    error_summary = transform_error_summary(errors)
    endpoint_stats = transform_api_metrics(api_calls)

    html = [
        "<html>",
        "<head><title>System Report</title></head>",
        "<body>",
        "<h1>Error Summary</h1>",
        "<ul>",
    ]

    for msg, count in error_summary.items():
        html.append(f"<li><b>{msg}</b>: {count} occurrences</li>")

    html.extend(
        [
            "</ul>",
            "<h2>API Latency</h2>",
            "<table border='1'>",
            "<tr><th>Endpoint</th><th>Avg (ms)</th></tr>",
        ]
    )

    for endpoint, times in endpoint_stats.items():
        avg = sum(times) / len(times)
        html.append(f"<tr><td>{endpoint}</td><td>{round(avg, 1)}</td></tr>")

    html.extend(
        [
            "</table>",
            "<h2>Active Sessions</h2>",
            f"<p>{len(sessions)} user(s) currently active</p>",
            "</body>",
            "</html>",
        ]
    )

    return "\n".join(html)


def write_report(report_path: str, content: str) -> None:
    """
    Write HTML report to file.
    """
    with open(report_path, "w") as f:
        f.write(content)


def process_pipeline() -> None:
    """
    Main pipeline: Extract, Transform, Load log data and generate report.
    """
    # Extract
    error_entries, sessions, api_calls, _ = extract_logs(LOG_FILE)

    # Load to database
    load_to_db(DB_PATH, error_entries, api_calls)

    # Generate and write report
    report_content = generate_report(error_entries, api_calls, sessions)
    write_report(REPORT_PATH, report_content)

    print(f"Pipeline completed at {datetime.datetime.now()}")


if __name__ == "__main__":
    # Initialize sample log file if it doesn't exist (for testing)
    if not os.path.exists(LOG_FILE):
        os.makedirs(os.path.dirname(LOG_FILE) or ".", exist_ok=True)
        with open(LOG_FILE, "w") as f:
            f.write("2024-01-01 12:00:00 INFO User 42 logged in\n")
            f.write("2024-01-01 12:05:00 ERROR Database timeout\n")
            f.write("2024-01-01 12:05:05 ERROR Database timeout\n")
            f.write("2024-01-01 12:08:00 INFO API /users/profile took 250ms\n")
            f.write("2024-01-01 12:09:00 WARN Memory usage at 87%\n")
            f.write("2024-01-01 12:10:00 INFO User 42 logged out\n")

    process_pipeline()
