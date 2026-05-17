"""
This script processes server logs to generate an HTML report on system metrics.

It follows an Extract, Transform, Load (ETL) process:
1.  **Extract**: Reads log entries from a specified log file.
2.  **Transform**: Parses log entries, aggregates metrics (errors, API latency),
    and tracks user sessions.
3.  **Load**: Stores aggregated metrics in a SQLite database and generates
    an HTML report.

Configuration is managed via environment variables:
-   `LOG_FILE`: Path to the server log file.
-   `DB_PATH`: Path to the SQLite database file.
-   `REPORT_FILE`: Path to output the HTML report.
"""
import datetime
import os
import re
import sqlite3
from collections import defaultdict
from typing import Dict, List, Any, Optional, Tuple

# --- Configuration ---

# Default values are used if environment variables are not set.
LOG_FILE: str = os.getenv("LOG_FILE", "server.log")
DB_PATH: str = os.getenv("DB_PATH", "metrics.db")
REPORT_FILE: str = os.getenv("REPORT_FILE", "report.html")

# --- Type Definitions ---

LogEntry = Dict[str, Any]
ErrorSummary = Dict[str, int]
ApiMetrics = Dict[str, List[int]]
ActiveSessions = Dict[str, str]

# --- Log Parsing (Extract) ---

LOG_PATTERN = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) "
    r"(?P<level>INFO|ERROR|WARN) "
    r"(?P<message>.*)$"
)
USER_LOGGED_IN_PATTERN = re.compile(r"User (?P<user_id>\w+) logged in")
USER_LOGGED_OUT_PATTERN = re.compile(r"User (?P<user_id>\w+) logged out")
API_CALL_PATTERN = re.compile(r"API (?P<endpoint>/\S+) took (?P<duration>\d+)ms")


def extract_log_entries(log_file: str) -> List[LogEntry]:
    """
    Reads a log file and extracts structured data from each line.

    Args:
        log_file: The path to the log file.

    Returns:
        A list of dictionaries, where each dictionary represents a parsed log entry.
        Returns an empty list if the log file doesn't exist.
    """
    if not os.path.exists(log_file):
        print(f"Log file not found at {log_file}. Skipping.")
        return []

    entries: List[LogEntry] = []
    with open(log_file, "r") as f:
        for line in f:
            match = LOG_PATTERN.match(line)
            if match:
                entries.append(match.groupdict())
    return entries


# --- Data Processing (Transform) ---


def transform_data(
    entries: List[LogEntry],
) -> Tuple[ErrorSummary, ApiMetrics, ActiveSessions]:
    """
    Processes a list of log entries to aggregate metrics.

    Args:
        entries: A list of parsed log entries.

    Returns:
        A tuple containing:
        -   error_summary: A dictionary mapping error messages to their counts.
        -   api_metrics: A dictionary mapping API endpoints to a list of latencies.
        -   active_sessions: A dictionary of active user sessions.
    """
    error_summary: ErrorSummary = defaultdict(int)
    api_metrics: ApiMetrics = defaultdict(list)
    active_sessions: ActiveSessions = {}

    for entry in entries:
        level = entry["level"]
        message = entry["message"]
        timestamp = entry["timestamp"]

        if level == "ERROR":
            error_summary[message] += 1
        elif level == "INFO":
            user_login = USER_LOGGED_IN_PATTERN.match(message)
            if user_login:
                user_id = user_login.group("user_id")
                active_sessions[user_id] = timestamp
                continue

            user_logout = USER_LOGGED_OUT_PATTERN.match(message)
            if user_logout:
                user_id = user_logout.group("user_id")
                if user_id in active_sessions:
                    del active_sessions[user_id]
                continue

            api_call = API_CALL_PATTERN.match(message)
            if api_call:
                endpoint = api_call.group("endpoint")
                duration = int(api_call.group("duration"))
                api_metrics[endpoint].append(duration)

    return error_summary, api_metrics, active_sessions


# --- Database and Reporting (Load) ---


def initialize_database(db_path: str) -> None:
    """
    Creates the database and necessary tables if they don't exist.

    Args:
        db_path: The path to the SQLite database file.
    """
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS errors (
                timestamp TEXT,
                message TEXT,
                count INTEGER
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS api_metrics (
                timestamp TEXT,
                endpoint TEXT,
                avg_latency_ms REAL
            )
            """
        )
        conn.commit()


def load_data_to_db(
    db_path: str, error_summary: ErrorSummary, api_metrics: ApiMetrics
) -> None:
    """
    Saves aggregated metrics to the SQLite database using parameterized queries.

    Args:
        db_path: The path to the SQLite database file.
        error_summary: A dictionary of error messages and their counts.
        api_metrics: A dictionary of API endpoints and their latencies.
    """
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        now = datetime.datetime.now().isoformat()

        # Safely insert error data
        error_data = [(now, msg, count) for msg, count in error_summary.items()]
        cursor.executemany(
            "INSERT INTO errors (timestamp, message, count) VALUES (?, ?, ?)",
            error_data,
        )

        # Calculate and safely insert API metrics
        api_data = []
        for endpoint, latencies in api_metrics.items():
            avg_latency = sum(latencies) / len(latencies) if latencies else 0
            api_data.append((now, endpoint, avg_latency))

        cursor.executemany(
            "INSERT INTO api_metrics (timestamp, endpoint, avg_latency_ms) VALUES (?, ?, ?)",
            api_data,
        )
        conn.commit()


def generate_html_report(
    error_summary: ErrorSummary,
    api_metrics: ApiMetrics,
    active_sessions: ActiveSessions,
    report_file: str,
) -> None:
    """
    Generates an HTML report from the processed data.

    Args:
        error_summary: A dictionary of error messages and their counts.
        api_metrics: A dictionary of API endpoints and their latencies.
        active_sessions: A dictionary of active user sessions.
        report_file: The path to write the HTML report to.
    """
    html = "<html><head><title>System Report</title></head><body>"
    html += "<h1>Error Summary</h1><ul>"
    for msg, count in error_summary.items():
        html += f"<li><b>{msg}</b>: {count} occurrences</li>"
    html += "</ul>"

    html += "<h2>API Latency</h2><table border='1'>"
    html += "<tr><th>Endpoint</th><th>Avg (ms)</th></tr>"
    for endpoint, latencies in api_metrics.items():
        avg = sum(latencies) / len(latencies) if latencies else 0
        html += f"<tr><td>{endpoint}</td><td>{avg:.1f}</td></tr>"
    html += "</table>"

    html += "<h2>Active Sessions</h2>"
    html += f"<p>{len(active_sessions)} user(s) currently active</p>"
    html += "</body></html>"

    with open(report_file, "w") as f:
        f.write(html)


def create_dummy_log_file_if_not_exists(log_file: str) -> None:
    """Creates a sample log file if one doesn't exist, for demonstration."""
    if not os.path.exists(log_file):
        print(f"Creating dummy log file at {log_file}")
        with open(log_file, "w") as f:
            f.write("2024-01-01 12:00:00 INFO User user1 logged in\n")
            f.write("2024-01-01 12:05:00 ERROR Database timeout\n")
            f.write("2024-01-01 12:05:05 ERROR Database timeout\n")
            f.write("2024-01-01 12:08:00 INFO API /users/profile took 250ms\n")
            f.write("2024-01-01 12:09:00 WARN Memory usage at 87%\n")
            f.write("2024-01-01 12:10:00 INFO User user1 logged out\n")


def main() -> None:
    """
    Main function to run the ETL pipeline.
    """
    print("Starting data processing pipeline...")
    create_dummy_log_file_if_not_exists(LOG_FILE)

    # 1. Extract
    log_entries = extract_log_entries(LOG_FILE)

    # 2. Transform
    errors, apis, sessions = transform_data(log_entries)

    # 3. Load
    initialize_database(DB_PATH)
    load_data_to_db(DB_PATH, errors, apis)
    generate_html_report(errors, apis, sessions, REPORT_FILE)

    print(f"Pipeline finished. Report generated at {REPORT_FILE}")


if __name__ == "__main__":
    main()
