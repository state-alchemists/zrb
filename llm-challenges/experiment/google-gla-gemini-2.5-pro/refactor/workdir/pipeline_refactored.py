
import os
import re
import sqlite3
import datetime
from collections import defaultdict
from typing import List, Dict, Tuple, Any, Optional

# --- Configuration ---
# Load configuration from environment variables with default fallbacks
DB_PATH = os.getenv("DB_PATH", "metrics.db")
LOG_FILE = os.getenv("LOG_FILE", "server.log")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", 5432))
DB_USER = os.getenv("DB_USER", "admin")
DB_PASS = os.getenv("DB_PASS", "dummy_password") # Secrets should not have defaults

# --- Log Parsing (Extract) ---
LOG_LINE_REGEX = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) "
    r"(?P<level>INFO|WARN|ERROR) "
    r"(?P<message>.*)$"
)

API_CALL_REGEX = re.compile(r"API (?P<endpoint>/\S+) took (?P<duration>\d+)ms")
USER_ACTION_REGEX = re.compile(r"User (?P<user_id>\d+) (?P<action>logged (in|out))")

def extract_log_data(log_file: str) -> List[Dict[str, Any]]:
    """
    Parses a log file and extracts structured data from each line.

    Args:
        log_file: The path to the server log file.

    Returns:
        A list of dictionaries, where each dictionary represents a parsed log entry.
        Returns an empty list if the file doesn't exist.
    """
    if not os.path.exists(log_file):
        print(f"Warning: Log file not found at {log_file}")
        return []

    parsed_data = []
    with open(log_file, "r") as f:
        for line in f:
            match = LOG_LINE_REGEX.match(line.strip())
            if not match:
                continue

            log_entry = match.groupdict()
            message = log_entry["message"]

            api_match = API_CALL_REGEX.search(message)
            if api_match:
                log_entry.update(api_match.groupdict())
                log_entry["duration"] = int(log_entry["duration"])
                log_entry["type"] = "API"

            user_match = USER_ACTION_REGEX.search(message)
            if user_match:
                log_entry.update(user_match.groupdict())
                log_entry["type"] = "USER"
            
            parsed_data.append(log_entry)
            
    return parsed_data

# --- Data Processing (Transform) ---
def transform_data(log_data: List[Dict[str, Any]]) -> Tuple[Dict[str, int], Dict[str, List[int]], int]:
    """
    Transforms raw log data into aggregated metrics.

    Args:
        log_data: A list of parsed log entries from extract_log_data.

    Returns:
        A tuple containing:
        - error_summary: A dictionary mapping error messages to their counts.
        - api_latency: A dictionary mapping API endpoints to a list of their latencies.
        - active_sessions: The number of currently active user sessions.
    """
    error_summary = defaultdict(int)
    api_latency = defaultdict(list)
    sessions = {}

    for entry in log_data:
        if entry["level"] == "ERROR":
            error_summary[entry["message"]] += 1
        
        elif entry.get("type") == "API":
            api_latency[entry["endpoint"]].append(entry["duration"])

        elif entry.get("type") == "USER":
            if entry["action"] == "logged in":
                sessions[entry["user_id"]] = entry["timestamp"]
            elif entry["action"] == "logged out" and entry["user_id"] in sessions:
                del sessions[entry["user_id"]]
    
    return dict(error_summary), dict(api_latency), len(sessions)


# --- Data Loading and Reporting (Load) ---
def load_data_and_generate_report(
    db_path: str,
    error_summary: Dict[str, int],
    api_latency: Dict[str, List[int]],
    active_sessions: int
):
    """
    Loads aggregated metrics into a database and generates an HTML report.

    Args:
        db_path: The path to the SQLite database file.
        error_summary: A dictionary of error messages and their counts.
        api_latency: A dictionary of API endpoints and their latencies.
        active_sessions: The count of active user sessions.
    """
    print(f"Connecting to database at {db_path}...")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create tables if they don't exist
    cursor.execute("CREATE TABLE IF NOT EXISTS errors (timestamp TEXT, message TEXT, count INTEGER)")
    cursor.execute("CREATE TABLE IF NOT EXISTS api_metrics (timestamp TEXT, endpoint TEXT, avg_latency REAL)")

    # Insert error data using parameterized queries
    timestamp = datetime.datetime.now().isoformat()
    error_data = [(timestamp, msg, count) for msg, count in error_summary.items()]
    cursor.executemany("INSERT INTO errors VALUES (?, ?, ?)", error_data)

    # Calculate average latency and insert using parameterized queries
    api_metrics_data = []
    for endpoint, latencies in api_latency.items():
        avg_latency = sum(latencies) / len(latencies) if latencies else 0
        api_metrics_data.append((timestamp, endpoint, avg_latency))
    
    cursor.executemany("INSERT INTO api_metrics VALUES (?, ?, ?)", api_metrics_data)

    conn.commit()
    conn.close()
    print("Database updated successfully.")

    # Generate HTML report
    html = "<html><head><title>System Report</title></head><body>"
    html += "<h1>Error Summary</h1><ul>"
    for msg, count in error_summary.items():
        html += f"<li><b>{msg}</b>: {count} occurrences</li>"
    html += "</ul>"

    html += "<h2>API Latency</h2><table border='1'>"
    html += "<tr><th>Endpoint</th><th>Avg (ms)</th></tr>"
    for endpoint, latencies in api_latency.items():
        avg_latency = sum(latencies) / len(latencies) if latencies else 0
        html += f"<tr><td>{endpoint}</td><td>{avg_latency:.1f}</td></tr>"
    html += "</table>"

    html += f"<h2>Active Sessions</h2><p>{active_sessions} user(s) currently active</p>"
    html += "</body></html>"

    with open("report.html", "w") as f:
        f.write(html)
    print("Report 'report.html' generated successfully.")


def create_dummy_log_file(log_file: str):
    """Creates a dummy log file if one doesn't exist."""
    if not os.path.exists(log_file):
        print(f"Creating dummy log file at {log_file}")
        with open(log_file, "w") as f:
            f.write("2024-01-01 12:00:00 INFO User 42 logged in\n")
            f.write("2024-01-01 12:05:00 ERROR Database timeout\n")
            f.write("2024-01-01 12:05:05 ERROR Database timeout\n")
            f.write("2024-01-01 12:08:00 INFO API /users/profile took 250ms\n")
            f.write("2024-01-01 12:09:00 WARN Memory usage at 87%\n")
            f.write("2024-01-01 12:10:00 INFO User 42 logged out\n")

# --- Main Execution ---
def main():
    """Main function to run the ETL pipeline."""
    print("Starting data processing pipeline...")
    
    # Create a dummy log file for demonstration if it doesn't exist
    create_dummy_log_file(LOG_FILE)
    
    # 1. Extract
    log_data = extract_log_data(LOG_FILE)
    
    # 2. Transform
    error_summary, api_latency, active_sessions = transform_data(log_data)
    
    # 3. Load
    load_data_and_generate_report(DB_PATH, error_summary, api_latency, active_sessions)
    
    print(f"Job finished at {datetime.datetime.now()}")

if __name__ == "__main__":
    main()
