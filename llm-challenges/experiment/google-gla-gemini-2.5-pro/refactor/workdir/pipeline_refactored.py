
import os
import re
import sqlite3
import datetime
from collections import defaultdict
from typing import List, Dict, Any, Tuple, Optional

# --- Configuration ---

def get_config() -> Dict[str, Any]:
    """
    Loads configuration from environment variables.
    Provides default values for local development.
    """
    return {
        "db_path": os.getenv("DB_PATH", "metrics.db"),
        "log_file": os.getenv("LOG_FILE", "server.log"),
    }

# --- Data Models (for clarity) ---

LogEntry = Dict[str, Any]
Metrics = Tuple[Dict[str, int], Dict[str, List[int]], int]

# --- 1. Extraction ---

def extract_log_data(log_file: str) -> List[LogEntry]:
    """
    Extracts and parses data from the server log file using regex.
    
    Args:
        log_file: Path to the log file.
        
    Returns:
        A list of dictionaries, where each dictionary represents a parsed log entry.
    """
    # Regex to capture the basic structure of a log line
    log_pattern = re.compile(
        r"^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) "
        r"(?P<level>ERROR|INFO|WARN) "
        r"(?P<message>.*)$"
    )
    
    # Specific patterns for different message types
    patterns = {
        "user": re.compile(r"User (?P<user_id>\d+) (?P<action>logged (in|out))"),
        "api": re.compile(r"API (?P<endpoint>\S+) took (?P<duration>\d+)ms"),
    }

    extracted_data = []
    if not os.path.exists(log_file):
        print(f"Warning: Log file not found at '{log_file}'")
        return extracted_data

    with open(log_file, "r") as f:
        for line in f:
            match = log_pattern.match(line.strip())
            if not match:
                continue

            log_entry = match.groupdict()
            
            if log_entry["level"] == "INFO":
                user_match = patterns["user"].search(log_entry["message"])
                if user_match:
                    log_entry.update(user_match.groupdict())
                    log_entry["type"] = "user_activity"
                
                api_match = patterns["api"].search(log_entry["message"])
                if api_match:
                    log_entry.update(api_match.groupdict())
                    log_entry["type"] = "api_call"

            extracted_data.append(log_entry)
            
    return extracted_data

# --- 2. Transformation ---

def transform_data(log_entries: List[LogEntry]) -> Metrics:
    """
    Transforms raw log data into structured metrics.
    
    Args:
        log_entries: A list of parsed log entries from extract_log_data.
        
    Returns:
        A tuple containing:
        - A dictionary of error messages and their counts.
        - A dictionary of API endpoints and their latency values.
        - An integer representing the number of active user sessions.
    """
    error_summary = defaultdict(int)
    api_latency = defaultdict(list)
    sessions = {} # Using a dictionary to track individual user sessions

    for entry in log_entries:
        level = entry.get("level")
        
        if level == "ERROR":
            error_summary[entry["message"]] += 1
        
        elif level == "INFO":
            entry_type = entry.get("type")
            if entry_type == "user_activity":
                user_id = entry.get("user_id")
                action = entry.get("action")
                if action == "logged in":
                    sessions[user_id] = entry["timestamp"]
                elif action == "logged out" and user_id in sessions:
                    del sessions[user_id]
            
            elif entry_type == "api_call":
                endpoint = entry.get("endpoint")
                duration = entry.get("duration")
                if endpoint and duration:
                    api_latency[endpoint].append(int(duration))

    return dict(error_summary), dict(api_latency), len(sessions)

# --- 3. Loading ---

def load_to_database(db_path: str, error_summary: Dict[str, int], api_latency: Dict[str, List[int]]) -> None:
    """
    Loads aggregated metrics into the SQLite database.
    
    This function connects to the database, creates tables if they don't exist,
    and inserts the latest metrics using parameterized queries to prevent SQL injection.
    
    Args:
        db_path: Path to the SQLite database file.
        error_summary: Dictionary of error messages and counts.
        api_latency: Dictionary of API endpoints and latencies.
    """
    try:
        with sqlite3.connect(db_path) as conn:
            c = conn.cursor()
            
            # Create tables if they don't exist
            c.execute("""
                CREATE TABLE IF NOT EXISTS errors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    message TEXT NOT NULL,
                    count INTEGER NOT NULL
                )
            """)
            c.execute("""
                CREATE TABLE IF NOT EXISTS api_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    endpoint TEXT NOT NULL,
                    avg_ms REAL NOT NULL
                )
            """)

            # Insert error summary data
            timestamp = datetime.datetime.now().isoformat()
            errors_to_insert = [
                (timestamp, msg, count) for msg, count in error_summary.items()
            ]
            if errors_to_insert:
                c.executemany(
                    "INSERT INTO errors (timestamp, message, count) VALUES (?, ?, ?)",
                    errors_to_insert
                )

            # Insert API latency data
            api_metrics_to_insert = []
            for ep, times in api_latency.items():
                if times:
                    avg = sum(times) / len(times)
                    api_metrics_to_insert.append((timestamp, ep, avg))
            
            if api_metrics_to_insert:
                c.executemany(
                    "INSERT INTO api_metrics (timestamp, endpoint, avg_ms) VALUES (?, ?, ?)",
                    api_metrics_to_insert
                )

            conn.commit()
            print(f"Successfully loaded data into '{db_path}'")

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

def generate_report(error_summary: Dict[str, int], api_latency: Dict[str, List[int]], active_sessions: int) -> None:
    """
    Generates an HTML report from the metrics.
    
    Args:
        error_summary: Dictionary of error messages and counts.
        api_latency: Dictionary of API endpoints and latencies.
        active_sessions: Count of active user sessions.
    """
    
    def generate_error_list(summary: Dict[str, int]) -> str:
        items = [f"<li><b>{msg}</b>: {count} occurrences</li>" for msg, count in summary.items()]
        return "\n".join(items)
        
    def generate_latency_table(latency: Dict[str, List[int]]) -> str:
        rows = []
        for ep, times in latency.items():
            if times:
                avg = sum(times) / len(times)
                rows.append(f"<tr><td>{ep}</td><td>{avg:.1f}</td></tr>")
        return "\n".join(rows)

    html_template = f"""
<html>
<head>
    <title>System Report</title>
    <style>
        body {{ font-family: sans-serif; margin: 2em; }}
        h1, h2 {{ color: #333; }}
        table {{ border-collapse: collapse; width: 50%; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #f2f2f2; }}
    </style>
</head>
<body>
    <h1>Error Summary</h1>
    <ul>
        {generate_error_list(error_summary)}
    </ul>
    
    <h2>API Latency</h2>
    <table border='1'>
        <tr>
            <th>Endpoint</th>
            <th>Avg (ms)</th>
        </tr>
        {generate_latency_table(api_latency)}
    </table>
    
    <h2>Active Sessions</h2>
    <p>{active_sessions} user(s) currently active</p>
    
    <p><small>Report generated at {datetime.datetime.now()}</small></p>
</body>
</html>
    """

    try:
        with open("report.html", "w") as f:
            f.write(html_template.strip())
        print("Successfully generated HTML report 'report.html'")
    except IOError as e:
        print(f"Error writing HTML report: {e}")

# --- Main Orchestration ---

def create_dummy_log_if_not_exists(log_file: str) -> None:
    """Creates a dummy log file for demonstration if it doesn't exist."""
    if not os.path.exists(log_file):
        print(f"'{log_file}' not found. Creating a dummy log file.")
        with open(log_file, "w") as f:
            f.write("2024-01-01 12:00:00 INFO User 42 logged in\n")
            f.write("2024-01-01 12:05:00 ERROR Database timeout\n")
            f.write("2024-01-01 12:05:05 ERROR Database timeout\n")
            f.write("2024-01-01 12:08:00 INFO API /users/profile took 250ms\n")
            f.write("2024-01-01 12:09:00 WARN Memory usage at 87%\n")
            f.write("2024-01-01 12:10:00 INFO User 42 logged out\n")

def main():
    """Main function to run the ETL pipeline."""
    print(f"Pipeline started at {datetime.datetime.now()}")
    
    config = get_config()
    log_file = config["log_file"]
    db_path = config["db_path"]
    
    create_dummy_log_if_not_exists(log_file)
    
    # ETL Process
    log_data = extract_log_data(log_file)
    error_summary, api_latency, active_sessions = transform_data(log_data)
    load_to_database(db_path, error_summary, api_latency)
    generate_report(error_summary, api_latency, active_sessions)
    
    print(f"Pipeline finished at {datetime.datetime.now()}")

if __name__ == "__main__":
    main()
