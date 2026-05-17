
import os
import re
import sqlite3
import datetime
from collections import defaultdict
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional

# --- Configuration ---
# Load configuration from environment variables with sensible defaults.
DB_PATH = os.getenv("DB_PATH", "metrics.db")
LOG_FILE_PATH = os.getenv("LOG_FILE_PATH", "server.log")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_USER = os.getenv("DB_USER", "admin")
DB_PASS = os.getenv("DB_PASS") # No default for password

# --- Data Structures ---
# Using dataclasses for structured, immutable log entries.
@dataclass(frozen=True)
class LogEntry:
    timestamp: datetime.datetime
    level: str
    message: str

@dataclass(frozen=True)
class ErrorLog(LogEntry):
    pass

@dataclass(frozen=True)
class UserActivityLog(LogEntry):
    user_id: str
    action: str

@dataclass(frozen=True)
class ApiCallLog(LogEntry):
    endpoint: str
    duration_ms: int

# --- 1. Extract Phase ---
def extract_log_data(log_file_path: str) -> List[LogEntry]:
    """
    Parses a log file and extracts structured log entries.

    Args:
        log_file_path: The path to the server log file.

    Returns:
        A list of parsed LogEntry objects.
    """
    if not os.path.exists(log_file_path):
        print(f"Warning: Log file not found at '{log_file_path}'.")
        return []

    # Regex patterns for different log line formats
    log_pattern = re.compile(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) (INFO|ERROR|WARN) (.*)")
    user_pattern = re.compile(r"User (\w+) (logged in|logged out)")
    api_pattern = re.compile(r"API ([\/\w]+) took (\d+)ms")

    parsed_logs: List[LogEntry] = []
    with open(log_file_path, "r") as f:
        for line in f:
            match = log_pattern.match(line)
            if not match:
                continue

            timestamp_str, level, message = match.groups()
            timestamp = datetime.datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
            message = message.strip()
            
            log_entry: Optional[LogEntry] = None

            if level == "ERROR":
                log_entry = ErrorLog(timestamp=timestamp, level=level, message=message)
            elif level == "INFO":
                user_match = user_pattern.search(message)
                if user_match:
                    user_id, action = user_match.groups()
                    log_entry = UserActivityLog(timestamp=timestamp, level=level, message=message, user_id=user_id, action=action)
                
                api_match = api_pattern.search(message)
                if api_match:
                    endpoint, duration_ms_str = api_match.groups()
                    log_entry = ApiCallLog(timestamp=timestamp, level=level, message=message, endpoint=endpoint, duration_ms=int(duration_ms_str))
            
            if log_entry:
                parsed_logs.append(log_entry)

    return parsed_logs

# --- 2. Transform Phase ---
def transform_data(logs: List[LogEntry]) -> Tuple[Dict[str, int], Dict[str, float], int]:
    """
    Analyzes structured log data to produce metrics.

    Args:
        logs: A list of LogEntry objects.

    Returns:
        A tuple containing:
        - error_summary: A dictionary mapping error messages to their counts.
        - api_latency: A dictionary mapping API endpoints to average latency in ms.
        - active_sessions: The number of currently active user sessions.
    """
    error_summary: Dict[str, int] = defaultdict(int)
    api_calls: Dict[str, List[int]] = defaultdict(list)
    sessions: Dict[str, datetime.datetime] = {}

    for log in logs:
        if isinstance(log, ErrorLog):
            error_summary[log.message] += 1
        elif isinstance(log, ApiCallLog):
            api_calls[log.endpoint].append(log.duration_ms)
        elif isinstance(log, UserActivityLog):
            if "logged in" in log.action:
                sessions[log.user_id] = log.timestamp
            elif "logged out" in log.action and log.user_id in sessions:
                del sessions[log.user_id]

    api_latency: Dict[str, float] = {
        endpoint: sum(durations) / len(durations)
        for endpoint, durations in api_calls.items()
    }
    
    active_sessions = len(sessions)

    return error_summary, api_latency, active_sessions

# --- 3. Load Phase ---
def load_metrics_to_db(db_path: str, error_summary: Dict[str, int], api_latency: Dict[str, float]):
    """
    Connects to an SQLite database and stores the computed metrics.
    Uses parameterized queries to prevent SQL injection.

    Args:
        db_path: The path to the SQLite database file.
        error_summary: A dictionary of error messages and their counts.
        api_latency: A dictionary of API endpoints and their average latency.
    """
    print(f"Connecting to database at '{db_path}'...")
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        
        # Create tables if they don't exist
        cursor.execute("CREATE TABLE IF NOT EXISTS errors (dt TEXT, message TEXT, count INTEGER)")
        cursor.execute("CREATE TABLE IF NOT EXISTS api_metrics (dt TEXT, endpoint TEXT, avg_ms REAL)")

        # Insert error metrics
        now = datetime.datetime.now().isoformat()
        error_data = [(now, msg, count) for msg, count in error_summary.items()]
        cursor.executemany("INSERT INTO errors VALUES (?, ?, ?)", error_data)

        # Insert API metrics
        api_data = [(now, endpoint, avg) for endpoint, avg in api_latency.items()]
        cursor.executemany("INSERT INTO api_metrics VALUES (?, ?, ?)", api_data)

        conn.commit()
    print("Metrics successfully loaded to the database.")

def generate_html_report(error_summary: Dict[str, int], api_latency: Dict[str, float], active_sessions: int):
    """
    Generates an HTML report from the metrics.

    Args:
        error_summary: A dictionary of error messages and their counts.
        api_latency: A dictionary of API endpoints and their average latency.
        active_sessions: The number of active user sessions.
    """
    report_html = "<html>\n<head><title>System Report</title></head>\n<body>\n"
    
    # Error Summary section
    report_html += "<h1>Error Summary</h1>\n<ul>\n"
    for err_msg, count in error_summary.items():
        report_html += f"<li><b>{err_msg}</b>: {count} occurrences</li>\n"
    report_html += "</ul>\n"

    # API Latency section
    report_html += "<h2>API Latency</h2>\n<table border='1'>\n"
    report_html += "<tr><th>Endpoint</th><th>Avg (ms)</th></tr>\n"
    for endpoint, avg in api_latency.items():
        report_html += f"<tr><td>{endpoint}</td><td>{round(avg, 1)}</td></tr>\n"
    report_html += "</table>\n"

    # Active Sessions section
    report_html += "<h2>Active Sessions</h2>\n"
    report_html += f"<p>{active_sessions} user(s) currently active</p>\n"
    
    report_html += "</body>\n</html>"

    with open("report.html", "w") as f:
        f.write(report_html)
    print("HTML report 'report.html' generated.")

# --- Orchestration ---
def main():
    """Main function to run the ETL pipeline."""
    print("Starting data processing pipeline...")

    # Create a dummy log file if it doesn't exist, for demonstration purposes.
    if not os.path.exists(LOG_FILE_PATH):
        print(f"Creating dummy log file at '{LOG_FILE_PATH}'")
        with open(LOG_FILE_PATH, "w") as f:
            f.write("2024-01-01 12:00:00 INFO User 42 logged in\\n")
            f.write("2024-01-01 12:05:00 ERROR Database timeout\\n")
            f.write("2024-01-01 12:05:05 ERROR Database timeout\\n")
            f.write("2024-01-01 12:08:00 INFO API /users/profile took 250ms\\n")
            f.write("2024-01-01 12:09:00 WARN Memory usage at 87%\\n")
            f.write("2024-01-01 12:10:00 INFO User 42 logged out\\n")

    # 1. Extract
    log_data = extract_log_data(LOG_FILE_PATH)

    # 2. Transform
    error_summary, api_latency, active_sessions = transform_data(log_data)

    # 3. Load
    load_metrics_to_db(DB_PATH, error_summary, api_latency)
    generate_html_report(error_summary, api_latency, active_sessions)

    print(f"Job finished at {datetime.datetime.now()}")

if __name__ == "__main__":
    # A simple check for the DB password, though in a real app
    # this would be handled by a more robust configuration system.
    if DB_PASS is None:
        print("Warning: DB_PASS environment variable not set.")
    
    main()
