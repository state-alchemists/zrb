"""
Refactored log processing pipeline.

This script reads server logs, processes them to extract key metrics,
loads the metrics into a SQLite database, and generates an HTML report.

It follows an Extract-Transform-Load (ETL) pattern.
"""

import datetime
import os
import re
import sqlite3
from collections import defaultdict
from typing import Dict, List, Any, Optional, Tuple

from dotenv import load_dotenv

# --- Configuration ---

load_dotenv()

DB_PATH: str = os.getenv("DB_PATH", "metrics.db")
LOG_FILE: str = os.getenv("LOG_FILE", "server.log")
REPORT_PATH: str = os.getenv("REPORT_PATH", "report.html")
# DB_HOST, DB_PORT, DB_USER, DB_PASS are in .env but not used by sqlite3
# They are kept for compatibility if we switch to a server-based DB.


# --- Type Definitions ---

LogEntry = Dict[str, Any]
ErrorSummary = Dict[str, int]
ApiLatency = Dict[str, float]
ActiveSessions = int


# --- 1. Extract Phase ---

def extract_log_data(log_file: str) -> List[LogEntry]:
    """
    Parses a log file using regex and extracts structured data.

    Args:
        log_file: Path to the log file.

    Returns:
        A list of dictionaries, where each dictionary represents
        a structured log entry.
    """
    if not os.path.exists(log_file):
        print(f"Warning: Log file not found at {log_file}")
        return []

    # Regex to capture timestamp, level, and message
    log_pattern = re.compile(
        r"^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) "
        r"(?P<level>\w+) "
        r"(?P<message>.*)$"
    )
    # More specific patterns for different message types
    patterns = {
        "user_session": re.compile(r"User (?P<uid>\d+) (?P<action>logged (in|out))"),
        "api_call": re.compile(r"API (?P<endpoint>\S+) took (?P<duration>\d+)ms"),
    }

    extracted_data: List[LogEntry] = []
    with open(log_file, "r") as f:
        for line in f:
            match = log_pattern.match(line)
            if not match:
                continue

            data = match.groupdict()
            msg = data["message"]

            if data["level"] == "INFO":
                user_match = patterns["user_session"].search(msg)
                if user_match:
                    data.update(user_match.groupdict())
                    data["type"] = "user_session"
                
                api_match = patterns["api_call"].search(msg)
                if api_match:
                    data.update(api_match.groupdict())
                    data["duration"] = int(data["duration"])
                    data["type"] = "api_call"
            
            elif data["level"] in ("ERROR", "WARN"):
                data["type"] = data["level"].lower()

            extracted_data.append(data)
            
    return extracted_data


# --- 2. Transform Phase ---

def transform_data(log_data: List[LogEntry]) -> Tuple[ErrorSummary, ApiLatency, ActiveSessions]:
    """
    Transforms raw log data into aggregated metrics.

    Args:
        log_data: A list of parsed log entries from the extract phase.

    Returns:
        A tuple containing:
        - error_summary: A dictionary mapping error messages to their counts.
        - api_latency: A dictionary mapping API endpoints to avg latency.
        - active_sessions: The number of currently active user sessions.
    """
    error_summary: ErrorSummary = defaultdict(int)
    api_calls: Dict[str, List[int]] = defaultdict(list)
    sessions: Dict[str, str] = {}

    for entry in log_data:
        entry_type = entry.get("type")
        if entry_type == "error":
            error_summary[entry["message"]] += 1
        elif entry_type == "api_call":
            api_calls[entry["endpoint"]].append(entry["duration"])
        elif entry_type == "user_session":
            if entry["action"] == "logged in":
                sessions[entry["uid"]] = entry["timestamp"]
            elif entry["action"] == "logged out" and entry["uid"] in sessions:
                del sessions[entry["uid"]]

    api_latency: ApiLatency = {
        endpoint: sum(durations) / len(durations)
        for endpoint, durations in api_calls.items()
    }
    
    active_sessions = len(sessions)

    return error_summary, api_latency, active_sessions


# --- 3. Load Phase ---

def load_to_database(db_path: str, error_summary: ErrorSummary, api_latency: ApiLatency) -> None:
    """
    Loads aggregated metrics into a SQLite database.

    Args:
        db_path: The path to the SQLite database file.
        error_summary: A dictionary of error messages and their counts.
        api_latency: A dictionary of API endpoints and their average latency.
    """
    print(f"Connecting to database at {db_path}...")
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        
        # Create tables if they don't exist
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS errors (
                dt TEXT, 
                message TEXT, 
                count INTEGER,
                PRIMARY KEY (dt, message)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS api_metrics (
                dt TEXT, 
                endpoint TEXT, 
                avg_ms REAL,
                PRIMARY KEY (dt, endpoint)
            )
        """)

        now = datetime.datetime.now().isoformat()

        # Insert error data using parameterized queries to prevent SQL injection
        error_data = [(now, msg, count) for msg, count in error_summary.items()]
        cursor.executemany(
            "INSERT OR REPLACE INTO errors (dt, message, count) VALUES (?, ?, ?)",
            error_data
        )

        # Insert API metrics using parameterized queries
        api_data = [(now, ep, avg) for ep, avg in api_latency.items()]
        cursor.executemany(
            "INSERT OR REPLACE INTO api_metrics (dt, endpoint, avg_ms) VALUES (?, ?, ?)",
            api_data
        )
        
        conn.commit()
    print("Database load complete.")


def generate_html_report(
    report_path: str,
    error_summary: ErrorSummary,
    api_latency: ApiLatency,
    active_sessions: ActiveSessions,
) -> None:
    """
    Generates an HTML report from the processed data.

    Args:
        report_path: The path to save the HTML report.
        error_summary: A dictionary of error messages and their counts.
        api_latency: A dictionary of API endpoints and their average latency.
        active_sessions: The count of active user sessions.
    """
    html = "<html>\n<head><title>System Report</title></head>\n<body>\n"
    
    html += "<h1>Error Summary</h1>\n<ul>\n"
    for err_msg, count in error_summary.items():
        html += f"<li><b>{err_msg}</b>: {count} occurrences</li>\n"
    html += "</ul>\n"

    html += "<h2>API Latency</h2>\n<table border='1'>\n"
    html += "<tr><th>Endpoint</th><th>Avg (ms)</th></tr>\n"
    for ep, avg in api_latency.items():
        html += f"<tr><td>{ep}</td><td>{avg:.1f}</td></tr>\n"
    html += "</table>\n"

    html += "<h2>Active Sessions</h2>\n"
    html += f"<p>{active_sessions} user(s) currently active</p>\n"
    
    html += "</body>\n</html>"

    with open(report_path, "w") as f:
        f.write(html)
    print(f"Report generated at {report_path}")


def create_dummy_log_if_not_exists(log_file: str) -> None:
    """Creates a sample log file if one doesn't exist."""
    if not os.path.exists(log_file):
        print(f"Creating dummy log file at {log_file}...")
        with open(log_file, "w") as f:
            f.write("2024-01-01 12:00:00 INFO User 42 logged in\n")
            f.write("2024-01-01 12:05:00 ERROR Database timeout\n")
            f.write("2024-01-01 12:05:05 ERROR Database timeout\n")
            f.write("2024-01-01 12:08:00 INFO API /users/profile took 250ms\n")
            f.write("2024-01-01 12:09:00 WARN Memory usage at 87%\n")
            f.write("2024-01-01 12:10:00 INFO User 42 logged out\n")
            f.write("2024-01-01 12:11:00 INFO User 101 logged in\n")
            f.write("2024-01-01 12:12:00 INFO API /dashboard took 120ms\n")


def main() -> None:
    """Main function to run the ETL pipeline."""
    print("Starting pipeline...")
    
    create_dummy_log_if_not_exists(LOG_FILE)

    # 1. Extract
    log_data = extract_log_data(LOG_FILE)

    # 2. Transform
    error_summary, api_latency, active_sessions = transform_data(log_data)

    # 3. Load
    load_to_database(DB_PATH, error_summary, api_latency)
    generate_html_report(REPORT_PATH, error_summary, api_latency, active_sessions)
    
    print(f"Job finished at {datetime.datetime.now()}")


if __name__ == "__main__":
    main()
