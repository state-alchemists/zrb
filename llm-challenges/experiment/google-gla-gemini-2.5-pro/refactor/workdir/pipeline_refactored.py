
import os
import re
import sqlite3
import datetime
from typing import List, Dict, Tuple, Any

# --- CONFIGURATION ---
DB_PATH = os.environ.get("DB_PATH", "metrics.db")
LOG_FILE = os.environ.get("LOG_FILE", "server.log")
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = int(os.environ.get("DB_PORT", 5432))
DB_USER = os.environ.get("DB_USER", "admin")
DB_PASS = os.environ.get("DB_PASS", "password123") # In a real app, use a secret manager


def extract_data_from_log(log_path: str) -> List[Dict[str, Any]]:
    """
    Parses a log file and extracts structured data from each line.
    
    Args:
        log_path: The path to the log file.
        
    Returns:
        A list of dictionaries, where each dictionary represents a parsed log entry.
    """
    if not os.path.exists(log_path):
        return []

    # Regex patterns for different log entry types
    patterns = {
        "ERROR": re.compile(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) ERROR (.*)"),
        "INFO_USER": re.compile(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) INFO User (\w+) (logged in|logged out)"),
        "INFO_API": re.compile(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) INFO API ([\w/]+) took (\d+)ms"),
        "WARN": re.compile(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) WARN (.*)"),
    }

    parsed_data = []
    with open(log_path, "r") as f:
        for line in f:
            for key, pattern in patterns.items():
                match = pattern.match(line)
                if match:
                    timestamp_str, *groups = match.groups()
                    entry = {"timestamp": timestamp_str}
                    if key == "ERROR":
                        entry.update({"type": "ERROR", "message": groups[0]})
                    elif key == "INFO_USER":
                        entry.update({"type": "USER", "user_id": groups[0], "action": groups[1]})
                    elif key == "INFO_API":
                        entry.update({"type": "API", "endpoint": groups[0], "duration_ms": int(groups[1])})
                    elif key == "WARN":
                        entry.update({"type": "WARN", "message": groups[0]})
                    parsed_data.append(entry)
                    break
    return parsed_data


def transform_data(log_data: List[Dict[str, Any]]) -> Tuple[Dict[str, int], Dict[str, List[int]], int]:
    """
    Transforms raw log data into aggregated metrics.
    
    Args:
        log_data: A list of parsed log entries from extract_data_from_log.
        
    Returns:
        A tuple containing:
        - A dictionary of error messages and their counts.
        - A dictionary of API endpoints and a list of their latency values.
        - The number of currently active user sessions.
    """
    error_summary = {}
    api_latency = {}
    sessions = {}
    
    for entry in log_data:
        if entry["type"] == "ERROR":
            error_summary[entry["message"]] = error_summary.get(entry["message"], 0) + 1
        elif entry["type"] == "API":
            api_latency.setdefault(entry["endpoint"], []).append(entry["duration_ms"])
        elif entry["type"] == "USER":
            if entry["action"] == "logged in":
                sessions[entry["user_id"]] = entry["timestamp"]
            elif entry["action"] == "logged out" and entry["user_id"] in sessions:
                del sessions[entry["user_id"]]
                
    active_sessions = len(sessions)
    return error_summary, api_latency, active_sessions


def load_data_to_db(db_path: str, error_summary: Dict[str, int], api_latency: Dict[str, List[int]]):
    """
    Loads aggregated metrics into a SQLite database.
    
    Args:
        db_path: Path to the SQLite database file.
        error_summary: Dictionary of error messages and their counts.
        api_latency: Dictionary of API endpoints and their latency values.
    """
    print(f"Connecting to database at {db_path}...")
    with sqlite3.connect(db_path) as conn:
        c = conn.cursor()
        c.execute("CREATE TABLE IF NOT EXISTS errors (timestamp TEXT, message TEXT, count INTEGER)")
        c.execute("CREATE TABLE IF NOT EXISTS api_metrics (timestamp TEXT, endpoint TEXT, avg_ms REAL)")

        now = datetime.datetime.now().isoformat()

        # Safely insert error data
        errors_to_insert = [(now, msg, count) for msg, count in error_summary.items()]
        c.executemany("INSERT INTO errors VALUES (?, ?, ?)", errors_to_insert)

        # Calculate and safely insert API metrics
        api_metrics_to_insert = []
        for endpoint, times in api_latency.items():
            avg_latency = sum(times) / len(times) if times else 0
            api_metrics_to_insert.append((now, endpoint, avg_latency))
        c.executemany("INSERT INTO api_metrics VALUES (?, ?, ?)", api_metrics_to_insert)
        
        conn.commit()
    print("Data loaded to database.")


def generate_html_report(error_summary: Dict[str, int], api_latency: Dict[str, List[int]], active_sessions: int, output_path: str = "report.html"):
    """
    Generates an HTML report from the processed data.
    
    Args:
        error_summary: Dictionary of error messages and their counts.
        api_latency: Dictionary of API endpoints and their latency values.
        active_sessions: The number of active user sessions.
        output_path: The file path to write the HTML report to.
    """
    html_content = "<html>\n<head><title>System Report</title></head>\n<body>\n"
    html_content += "<h1>Error Summary</h1>\n<ul>\n"
    for err_msg, count in error_summary.items():
        html_content += f"<li><b>{err_msg}</b>: {count} occurrences</li>\n"
    html_content += "</ul>\n"

    html_content += "<h2>API Latency</h2>\n<table border='1'>\n"
    html_content += "<tr><th>Endpoint</th><th>Avg (ms)</th></tr>\n"
    for endpoint, times in api_latency.items():
        avg = sum(times) / len(times) if times else 0
        html_content += f"<tr><td>{endpoint}</td><td>{round(avg, 1)}</td></tr>\n"
    html_content += "</table>\n"

    html_content += f"<h2>Active Sessions</h2>\n<p>{active_sessions} user(s) currently active</p>\n"
    html_content += "</body>\n</html>"

    with open(output_path, "w") as f:
        f.write(html_content)
    print(f"Report generated at {output_path}")


def create_dummy_log_file(log_path: str):
    """Creates a dummy log file if one doesn't exist."""
    if not os.path.exists(log_path):
        print(f"Creating dummy log file at {log_path}")
        with open(log_path, "w") as f:
            f.write("2024-01-01 12:00:00 INFO User 42 logged in\n")
            f.write("2024-01-01 12:05:00 ERROR Database timeout\n")
            f.write("2024-01-01 12:05:05 ERROR Database timeout\n")
            f.write("2024-01-01 12:08:00 INFO API /users/profile took 250ms\n")
            f.write("2024-01-01 12:09:00 WARN Memory usage at 87%\n")
            f.write("2024-01-01 12:10:00 INFO User 42 logged out\n")


def main():
    """Main function to run the ETL pipeline."""
    create_dummy_log_file(LOG_FILE)
    
    # ETL Process
    log_data = extract_data_from_log(LOG_FILE)
    error_summary, api_latency, active_sessions = transform_data(log_data)
    load_data_to_db(DB_PATH, error_summary, api_latency)
    generate_html_report(error_summary, api_latency, active_sessions)
    
    print("Job finished at " + str(datetime.datetime.now()))


if __name__ == "__main__":
    main()
