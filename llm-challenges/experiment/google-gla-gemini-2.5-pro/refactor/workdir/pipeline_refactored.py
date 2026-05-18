
"""
Refactored log processing pipeline.

This script reads server logs, processes them to extract key metrics,
loads the metrics into a SQLite database, and generates an HTML report.
"""

import datetime
import os
import re
import sqlite3
from typing import Dict, List, Any, Optional, Tuple, NamedTuple
from dotenv import load_dotenv

# --- Data Structures ---

class LogEntry(NamedTuple):
    """Represents a single parsed log entry."""
    timestamp: datetime.datetime
    level: str
    message: str

class ApiCall(NamedTuple):
    """Represents an API call record."""
    endpoint: str
    duration_ms: int

class UserSession(NamedTuple):
    """Represents a user session event."""
    user_id: str
    action: str

class ErrorSummary(NamedTuple):
    """Represents a summary of error occurrences."""
    message: str
    count: int

# --- Configuration ---

def get_config() -> Dict[str, Any]:
    """
    Loads configuration from environment variables.

    Returns:
        A dictionary containing the configuration values.
    """
    load_dotenv()
    return {
        "db_path": os.getenv("DB_PATH", "metrics.db"),
        "log_file": os.getenv("LOG_FILE", "server.log"),
        "db_host": os.getenv("DB_HOST", "localhost"),
        "db_port": int(os.getenv("DB_PORT", 5432)),
        "db_user": os.getenv("DB_USER", "admin"),
    }

# --- Extract ---

def extract_log_data(log_file_path: str) -> List[LogEntry]:
    """
    Extracts and parses log data from a file.

    Args:
        log_file_path: The path to the log file.

    Returns:
        A list of LogEntry objects.
    """
    if not os.path.exists(log_file_path):
        return []

    log_pattern = re.compile(
        r"^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) "
        r"(?P<level>\w+) "
        r"(?P<message>.*)$"
    )
    
    log_entries = []
    with open(log_file_path, "r") as f:
        for line in f:
            match = log_pattern.match(line)
            if match:
                data = match.groupdict()
                log_entries.append(
                    LogEntry(
                        timestamp=datetime.datetime.strptime(
                            data["timestamp"], "%Y-%m-%d %H:%M:%S"
                        ),
                        level=data["level"],
                        message=data["message"].strip(),
                    )
                )
    return log_entries

# --- Transform ---

def transform_data(log_entries: List[LogEntry]) -> Tuple[List[ErrorSummary], List[ApiCall], int]:
    """
    Transforms raw log entries into structured metrics.

    Args:
        log_entries: A list of LogEntry objects.

    Returns:
        A tuple containing:
        - A list of error summaries.
        - A list of API calls.
        - The number of active user sessions.
    """
    errors: Dict[str, int] = {}
    api_calls: List[ApiCall] = []
    sessions: Dict[str, datetime.datetime] = {}

    user_pattern = re.compile(r"User (?P<user_id>\w+) (?P<action>logged (in|out))")
    api_pattern = re.compile(r"API (?P<endpoint>\S+) took (?P<duration>\d+)ms")

    for entry in log_entries:
        if entry.level == "ERROR":
            errors[entry.message] = errors.get(entry.message, 0) + 1
        
        elif entry.level == "INFO":
            user_match = user_pattern.search(entry.message)
            if user_match:
                data = user_match.groupdict()
                if data["action"] == "logged in":
                    sessions[data["user_id"]] = entry.timestamp
                elif data["action"] == "logged out" and data["user_id"] in sessions:
                    del sessions[data["user_id"]]
            
            api_match = api_pattern.search(entry.message)
            if api_match:
                data = api_match.groupdict()
                api_calls.append(
                    ApiCall(endpoint=data["endpoint"], duration_ms=int(data["duration"]))
                )

    error_summary = [ErrorSummary(msg, count) for msg, count in errors.items()]
    return error_summary, api_calls, len(sessions)

# --- Load ---

def load_data_to_db(db_path: str, errors: List[ErrorSummary], api_calls: List[ApiCall]):
    """
    Loads processed metrics into the database.

    Args:
        db_path: The path to the SQLite database file.
        errors: A list of error summaries.
        api_calls: A list of API calls.
    """
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        
        # Create tables
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

        # Insert error data
        now = datetime.datetime.now().isoformat()
        error_data = [(now, err.message, err.count) for err in errors]
        cursor.executemany("INSERT INTO errors VALUES (?, ?, ?)", error_data)

        # Calculate and insert API metrics
        endpoint_stats: Dict[str, List[int]] = {}
        for call in api_calls:
            endpoint_stats.setdefault(call.endpoint, []).append(call.duration_ms)
        
        api_metrics_data = []
        for endpoint, durations in endpoint_stats.items():
            avg_duration = sum(durations) / len(durations)
            api_metrics_data.append((now, endpoint, avg_duration))
        
        cursor.executemany("INSERT INTO api_metrics VALUES (?, ?, ?)", api_metrics_data)
        conn.commit()

# --- Reporting ---

def generate_html_report(errors: List[ErrorSummary], api_calls: List[ApiCall], active_sessions: int):
    """
    Generates an HTML report from the processed data.

    Args:
        errors: A list of error summaries.
        api_calls: A list of API calls.
        active_sessions: The number of active user sessions.
    """
    # Calculate API latency for the report
    endpoint_stats: Dict[str, List[int]] = {}
    for call in api_calls:
        endpoint_stats.setdefault(call.endpoint, []).append(call.duration_ms)

    # Build HTML content
    html = "<html><head><title>System Report</title></head><body>"
    html += "<h1>Error Summary</h1><ul>"
    for error in errors:
        html += f"<li><b>{error.message}</b>: {error.count} occurrences</li>"
    html += "</ul>"

    html += "<h2>API Latency</h2><table border='1'>"
    html += "<tr><th>Endpoint</th><th>Avg (ms)</th></tr>"
    for endpoint, durations in endpoint_stats.items():
        avg = sum(durations) / len(durations)
        html += f"<tr><td>{endpoint}</td><td>{round(avg, 1)}</td></tr>"
    html += "</table>"

    html += f"<h2>Active Sessions</h2><p>{active_sessions} user(s) currently active</p>"
    html += "</body></html>"

    with open("report.html", "w") as f:
        f.write(html)

# --- Main Orchestration ---

def create_dummy_log_file(log_file_path: str):
    """Creates a dummy log file if it doesn't exist."""
    if not os.path.exists(log_file_path):
        with open(log_file_path, "w") as f:
            f.write("2024-01-01 12:00:00 INFO User 42 logged in\n")
            f.write("2024-01-01 12:05:00 ERROR Database timeout\n")
            f.write("2024-01-01 12:05:05 ERROR Database timeout\n")
            f.write("2024-01-01 12:08:00 INFO API /users/profile took 250ms\n")
            f.write("2024-01-01 12:09:00 WARN Memory usage at 87%\n")
            f.write("2024-01-01 12:10:00 INFO User 42 logged out\n")

def main():
    """Main function to run the ETL pipeline."""
    print(f"Job started at {datetime.datetime.now()}")
    
    config = get_config()
    log_file = config["log_file"]
    db_path = config["db_path"]
    
    print(f"Connecting to {config['db_host']}:{config['db_port']} as {config['db_user']}...")

    # Create dummy log if needed
    create_dummy_log_file(log_file)
    
    # ETL Process
    log_entries = extract_log_data(log_file)
    errors, api_calls, active_sessions = transform_data(log_entries)
    load_data_to_db(db_path, errors, api_calls)
    generate_html_report(errors, api_calls, active_sessions)
    
    print(f"Job finished at {datetime.datetime.now()}")

if __name__ == "__main__":
    # Note: an external library is used to load the .env file.
    # To install it, run: pip install python-dotenv
    main()
