# pipeline_refactored.py
"""
Refactored log processing and reporting pipeline.

This script reads server logs, processes them to extract key metrics,
loads the metrics into a SQLite database, and generates an HTML report.

It follows an Extract-Transform-Load (ETL) pattern.
"""

import re
import sqlite3
import datetime
from collections import defaultdict
from typing import List, Dict, Tuple, Any, Optional

import config


# Regex patterns for parsing log lines
LOG_LINE_REGEX = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) "
    r"(?P<level>INFO|ERROR|WARN) "
    r"(?P<message>.*)$"
)
API_CALL_REGEX = re.compile(
    r"API (?P<endpoint>/\S+) took (?P<duration>\d+)ms"
)
USER_SESSION_REGEX = re.compile(
    r"User (?P<user_id>\w+) (?P<action>logged in|logged out)"
)


def extract_log_data(log_file: str) -> List[Dict[str, Any]]:
    """
    Extracts structured data from a log file.

    Args:
        log_file: Path to the log file.

    Returns:
        A list of dictionaries, each representing a parsed log entry.
    """
    parsed_data = []
    try:
        with open(log_file, "r") as f:
            for line in f:
                match = LOG_LINE_REGEX.match(line)
                if not match:
                    continue

                log_entry = match.groupdict()
                parsed_data.append(log_entry)
    except FileNotFoundError:
        print(f"Error: Log file not found at {log_file}")
    return parsed_data


def transform_data(log_data: List[Dict[str, Any]]) -> Tuple[Dict[str, int], Dict[str, float], int]:
    """
    Transforms raw log data into aggregated metrics.

    Args:
        log_data: A list of parsed log entries.

    Returns:
        A tuple containing:
        - A dictionary of error messages and their counts.
        - A dictionary of API endpoints and their average latency.
        - The number of active user sessions.
    """
    error_counts = defaultdict(int)
    api_latencies = defaultdict(list)
    active_sessions = set()

    for entry in log_data:
        if entry["level"] == "ERROR":
            error_counts[entry["message"].strip()] += 1

        elif entry["level"] == "INFO":
            api_match = API_CALL_REGEX.search(entry["message"])
            if api_match:
                endpoint = api_match.group("endpoint")
                duration = int(api_match.group("duration"))
                api_latencies[endpoint].append(duration)

            user_match = USER_SESSION_REGEX.search(entry["message"])
            if user_match:
                user_id = user_match.group("user_id")
                action = user_match.group("action")
                if action == "logged in":
                    active_sessions.add(user_id)
                elif action == "logged out" and user_id in active_sessions:
                    active_sessions.remove(user_id)

    avg_api_latency = {
        endpoint: sum(latencies) / len(latencies)
        for endpoint, latencies in api_latencies.items()
    }

    return dict(error_counts), avg_api_latency, len(active_sessions)


def load_metrics_to_db(db_path: str, errors: Dict[str, int], latencies: Dict[str, float]) -> None:
    """
    Loads aggregated metrics into a SQLite database.

    Args:
        db_path: Path to the SQLite database file.
        errors: A dictionary of error messages and their counts.
        latencies: A dictionary of API endpoints and their average latency.
    """
    print(f"Connecting to {config.DB_HOST}:{config.DB_PORT} as {config.DB_USER}...")
    with sqlite3.connect(db_path) as conn:
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

        now = datetime.datetime.now().isoformat()

        error_data = [(now, msg, count) for msg, count in errors.items()]
        cursor.executemany("INSERT INTO errors VALUES (?, ?, ?)", error_data)

        latency_data = [(now, endpoint, avg) for endpoint, avg in latencies.items()]
        cursor.executemany("INSERT INTO api_metrics VALUES (?, ?, ?)", latency_data)
        conn.commit()


def generate_html_report(
    errors: Dict[str, int],
    latencies: Dict[str, float],
    active_sessions: int,
    output_path: str = "report.html"
) -> None:
    """
    Generates an HTML report from the processed metrics.

    Args:
        errors: Dictionary of error messages and counts.
        latencies: Dictionary of API endpoints and average latency.
        active_sessions: Count of active user sessions.
        output_path: Path to write the HTML report.
    """
    html = "<html><head><title>System Report</title></head><body>"
    html += "<h1>Error Summary</h1><ul>"
    for msg, count in errors.items():
        html += f"<li><b>{msg}</b>: {count} occurrences</li>"
    html += "</ul>"

    html += "<h2>API Latency</h2><table border='1'>"
    html += "<tr><th>Endpoint</th><th>Avg (ms)</th></tr>"
    for endpoint, avg in latencies.items():
        html += f"<tr><td>{endpoint}</td><td>{avg:.1f}</td></tr>"
    html += "</table>"

    html += f"<h2>Active Sessions</h2><p>{active_sessions} user(s) currently active</p>"
    html += "</body></html>"

    with open(output_path, "w") as f:
        f.write(html)
    print(f"Report generated at {output_path}")


def main():
    """Main function to run the ETL pipeline."""
    # Create a dummy log file if it doesn't exist
    log_file_path = config.LOG_FILE
    if not log_file_path or not __import__("os").path.exists(log_file_path):
        with open(log_file_path, "w") as f:
            f.write("2024-01-01 12:00:00 INFO User 42 logged in\n")
            f.write("2024-01-01 12:05:00 ERROR Database timeout\n")
            f.write("2024-01-01 12:05:05 ERROR Database timeout\n")
            f.write("2024-01-01 12:08:00 INFO API /users/profile took 250ms\n")
            f.write("2024-01-01 12:09:00 WARN Memory usage at 87%\n")
            f.write("2024-01-01 12:10:00 INFO User 42 logged out\n")

    # E-T-L Process
    log_data = extract_log_data(config.LOG_FILE)
    errors, latencies, active_sessions = transform_data(log_data)
    load_metrics_to_db(config.DB_PATH, errors, latencies)
    generate_html_report(errors, latencies, active_sessions)

    print(f"Job finished at {datetime.datetime.now()}")


if __name__ == "__main__":
    main()
