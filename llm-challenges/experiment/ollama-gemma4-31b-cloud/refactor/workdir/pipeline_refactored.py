import datetime
import os
import re
import sqlite3
from typing import Dict, List, TypedDict, Optional, Tuple
from dataclasses import dataclass

# --- Configuration ---
# Load configuration from environment variables with defaults
DB_PATH = os.environ.get("DB_PATH", "metrics.db")
LOG_FILE = os.environ.get("LOG_FILE", "server.log")
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = os.environ.get("DB_PORT", "5432")
DB_USER = os.environ.get("DB_USER", "admin")
DB_PASS = os.environ.get("DB_PASS", "password123")

# --- Types ---
class ErrorEntry(TypedDict):
    timestamp: str
    message: str

class ApiCall(TypedDict):
    timestamp: str
    endpoint: str
    duration_ms: int

class UserSession(TypedDict):
    timestamp: str

@dataclass
class ProcessedData:
    error_counts: Dict[str, int]
    api_latencies: Dict[str, List[int]]
    active_sessions_count: int

# --- Logic ---

def extract_logs(file_path: str) -> Tuple[List[ErrorEntry], List[ApiCall], int]:
    """
    Parses the log file using regex to extract errors, API calls and track sessions.
    
    Args:
        file_path: Path to the server log file.
        
    Returns:
        A tuple containing:
        - A list of error entries.
        - A list of API call records.
        - The number of active sessions at the end of the log.
    """
    errors: List[ErrorEntry] = []
    api_calls: List[ApiCall] = []
    sessions: Dict[str, str] = {}

    # Regex patterns for different log levels
    # Format: YYYY-MM-DD HH:MM:SS LEVEL Message
    log_pattern = re.compile(r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) (\w+) (.*)$')
    user_pattern = re.compile(r'User (\S+) (logged in|logged out)')
    api_pattern = re.compile(r'API (\S+) took (\d+)ms')

    if not os.path.exists(file_path):
        return [], [], 0

    with open(file_path, "r") as f:
        for line in f:
            line = line.strip()
            match = log_pattern.match(line)
            if not match:
                continue

            timestamp, level, message = match.groups()

            if level == "ERROR":
                errors.append({"timestamp": timestamp, "message": message})
            
            elif level == "INFO":
                # Check for User activity
                user_match = user_pattern.search(message)
                if user_match:
                    uid, action = user_match.groups()
                    if action == "logged in":
                        sessions[uid] = timestamp
                    elif action == "logged out":
                        sessions.pop(uid, None)
                
                # Check for API activity
                api_match = api_pattern.search(message)
                if api_match:
                    endpoint, duration = api_match.groups()
                    api_calls.append({
                        "timestamp": timestamp, 
                        "endpoint": endpoint, 
                        "duration_ms": int(duration)
                    })
            
            # WARNINGs are matched by log_pattern but not specifically handled as 
            # separate categories in the original report's summary/DB logic.
            # Original code counted them in d_list but didn't use them in report/DB.

    return errors, api_calls, len(sessions)

def transform_data(errors: List[ErrorEntry], api_calls: List[ApiCall], sessions_count: int) -> ProcessedData:
    """
    Aggregates raw log data into summary statistics.
    
    Args:
        errors: Raw error entries.
        api_calls: Raw API call records.
        sessions_count: Number of active sessions.
        
    Returns:
        ProcessedData object containing aggregated metrics.
    """
    error_counts: Dict[str, int] = {}
    for err in errors:
        msg = err["message"]
        error_counts[msg] = error_counts.get(msg, 0) + 1

    api_latencies: Dict[str, List[int]] = {}
    for call in api_calls:
        ep = call["endpoint"]
        api_latencies.setdefault(ep, []).append(call["duration_ms"])

    return ProcessedData(
        error_counts=error_counts,
        api_latencies=api_latencies,
        active_sessions_count=sessions_count
    )

def load_to_db(data: ProcessedData) -> None:
    """
    Persists aggregated metrics into the SQLite database using parameterized queries.
    
    Args:
        data: The processed data to store.
    """
    print(f"Connecting to {DB_HOST}:{DB_PORT} as {DB_USER}...")
    
    now = datetime.datetime.now().isoformat()
    
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("CREATE TABLE IF NOT EXISTS errors (dt TEXT, message TEXT, count INTEGER)")
        c.execute("CREATE TABLE IF NOT EXISTS api_metrics (dt TEXT, endpoint TEXT, avg_ms REAL)")

        # Load errors
        for msg, count in data.error_counts.items():
            c.execute("INSERT INTO errors (dt, message, count) VALUES (?, ?, ?)", (now, msg, count))

        # Load API metrics
        for ep, times in data.api_latencies.items():
            avg = sum(times) / len(times) if times else 0
            c.execute("INSERT INTO api_metrics (dt, endpoint, avg_ms) VALUES (?, ?, ?)", (now, ep, avg))
        
        conn.commit()

def generate_report(data: ProcessedData) -> None:
    """
    Generates the HTML system report.
    
    Args:
        data: The processed data to report.
    """
    out = "<html>\n<head><title>System Report</title></head>\n<body>\n"
    out += "<h1>Error Summary</h1>\n<ul>\n"
    for err_msg, count in data.error_counts.items():
        out += f"<li><b>{err_msg}</b>: {count} occurrences</li>\n"
    out += "</ul>\n"

    out += "<h2>API Latency</h2>\n<table border='1'>\n"
    out += "<tr><th>Endpoint</th><th>Avg (ms)</th></tr>\n"
    for ep, times in data.api_latencies.items():
        avg = sum(times) / len(times) if times else 0
        out += f"<tr><td>{ep}</td><td>{round(avg, 1)}</td></tr>\n"
    out += "</table>\n"

    out += f"<h2>Active Sessions</h2>\n<p>{data.active_sessions_count} user(s) currently active</p>\n"
    out += "</body>\n</html>"

    with open("report.html", "w") as f:
        f.write(out)

def run_pipeline() -> None:
    """
    Main ETL orchestration function.
    """
    # Extract
    errors, api_calls, sessions_count = extract_logs(LOG_FILE)
    
    # Transform
    processed_data = transform_data(errors, api_calls, sessions_count)
    
    # Load
    load_to_db(processed_data)
    
    # Report
    generate_report(processed_data)
    
    print(f"Job finished at {datetime.datetime.now()}")

if __name__ == "__main__":
    # Setup dummy log if it doesn't exist for local testing consistency
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, "w") as f:
            f.write("2024-01-01 12:00:00 INFO User 42 logged in\n")
            f.write("2024-01-01 12:05:00 ERROR Database timeout\n")
            f.write("2024-01-01 12:05:05 ERROR Database timeout\n")
            f.write("2024-01-01 12:08:00 INFO API /users/profile took 250ms\n")
            f.write("2024-01-01 12:09:00 WARN Memory usage at 87%\n")
            f.write("2024-01-01 12:10:00 INFO User 42 logged out\n")
    
    run_pipeline()
