"""
Log processing pipeline.
Extracts metrics from server logs, loads them into a database, and generates an HTML report.
"""
import datetime
import os
import re
import sqlite3
from typing import Dict, List, Tuple

# Configuration with environment variables
DB_PATH: str = os.environ.get("DB_PATH", "metrics.db")
LOG_FILE: str = os.environ.get("LOG_FILE", "server.log")
DB_HOST: str = os.environ.get("DB_HOST", "localhost")
DB_PORT: int = int(os.environ.get("DB_PORT", "5432"))
DB_USER: str = os.environ.get("DB_USER", "admin")
DB_PASS: str = os.environ.get("DB_PASS", "password123")

# Regular expressions for parsing log lines
LOG_PATTERN = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s+([A-Z]+)\s+(.*)$")
USER_PATTERN = re.compile(r"^User\s+(\S+)\s+(.*)$")
API_PATTERN = re.compile(r"^API\s+(\S+)\s+took\s+(\d+)ms$")


def extract_logs(file_path: str) -> List[Tuple[str, str, str]]:
    """
    Reads the log file and extracts valid log entries using regex.
    
    Args:
        file_path: Path to the log file.
        
    Returns:
        A list of tuples containing (timestamp, level, message).
    """
    logs = []
    if not os.path.exists(file_path):
        return logs
        
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            match = LOG_PATTERN.match(line.strip())
            if match:
                timestamp, level, message = match.groups()
                logs.append((timestamp, level, message))
    return logs


def transform_data(
    logs: List[Tuple[str, str, str]]
) -> Tuple[Dict[str, int], Dict[str, float], int]:
    """
    Transforms log entries into aggregated metrics.
    
    Args:
        logs: List of parsed log tuples (timestamp, level, message).
        
    Returns:
        A tuple containing:
        - Dictionary of error messages and their counts.
        - Dictionary of API endpoints and their average latency in ms.
        - Integer count of active sessions.
    """
    error_counts: Dict[str, int] = {}
    sessions: Dict[str, str] = {}
    api_stats: Dict[str, List[int]] = {}

    for timestamp, level, message in logs:
        if level == "ERROR":
            error_counts[message] = error_counts.get(message, 0) + 1
            
        elif level == "INFO":
            user_match = USER_PATTERN.match(message)
            if user_match:
                uid, action = user_match.groups()
                if "logged in" in action:
                    sessions[uid] = timestamp
                elif "logged out" in action and uid in sessions:
                    sessions.pop(uid)
                continue
                
            api_match = API_PATTERN.match(message)
            if api_match:
                endpoint, duration_str = api_match.groups()
                api_stats.setdefault(endpoint, []).append(int(duration_str))

    api_averages: Dict[str, float] = {}
    for endpoint, times in api_stats.items():
        if times:
            api_averages[endpoint] = sum(times) / len(times)
            
    return error_counts, api_averages, len(sessions)


def load_to_db(
    db_path: str,
    db_host: str,
    db_port: int,
    db_user: str,
    error_counts: Dict[str, int],
    api_averages: Dict[str, float]
) -> None:
    """
    Loads aggregated metrics into the SQLite database.
    
    Args:
        db_path: Path to the SQLite database file.
        db_host: Database host (for logging).
        db_port: Database port (for logging).
        db_user: Database user (for logging).
        error_counts: Dictionary of error messages and their counts.
        api_averages: Dictionary of API endpoints and their average latency.
    """
    print(f"Connecting to {db_host}:{db_port} as {db_user}...")
    
    conn = sqlite3.connect(db_path)
    try:
        c = conn.cursor()
        c.execute("CREATE TABLE IF NOT EXISTS errors (dt TEXT, message TEXT, count INTEGER)")
        c.execute("CREATE TABLE IF NOT EXISTS api_metrics (dt TEXT, endpoint TEXT, avg_ms REAL)")
        
        now = str(datetime.datetime.now())
        
        for msg, count in error_counts.items():
            c.execute(
                "INSERT INTO errors VALUES (?, ?, ?)",
                (now, msg, count)
            )
            
        for endpoint, avg in api_averages.items():
            c.execute(
                "INSERT INTO api_metrics VALUES (?, ?, ?)",
                (now, endpoint, avg)
            )
            
        conn.commit()
    finally:
        conn.close()


def generate_report(
    error_counts: Dict[str, int],
    api_averages: Dict[str, float],
    active_sessions: int,
    output_file: str = "report.html"
) -> None:
    """
    Generates an HTML report from the aggregated metrics.
    
    Args:
        error_counts: Dictionary of error messages and their counts.
        api_averages: Dictionary of API endpoints and their average latency.
        active_sessions: Number of currently active sessions.
        output_file: Path to the output HTML file.
    """
    out = "<html>\n<head><title>System Report</title></head>\n<body>\n"
    out += "<h1>Error Summary</h1>\n<ul>\n"
    for err_msg, count in error_counts.items():
        out += f"<li><b>{err_msg}</b>: {count} occurrences</li>\n"
    out += "</ul>\n"

    out += "<h2>API Latency</h2>\n<table border='1'>\n"
    out += "<tr><th>Endpoint</th><th>Avg (ms)</th></tr>\n"
    for ep, avg in api_averages.items():
        out += f"<tr><td>{ep}</td><td>{round(avg, 1)}</td></tr>\n"
    out += "</table>\n"

    out += "<h2>Active Sessions</h2>\n"
    out += f"<p>{active_sessions} user(s) currently active</p>\n"
    out += "</body>\n</html>"
    
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(out)


def run_pipeline() -> None:
    """Runs the complete ETL pipeline."""
    logs = extract_logs(LOG_FILE)
    error_counts, api_averages, active_sessions = transform_data(logs)
    
    load_to_db(DB_PATH, DB_HOST, DB_PORT, DB_USER, error_counts, api_averages)
    
    generate_report(error_counts, api_averages, active_sessions)
    print(f"Job finished at {datetime.datetime.now()}")


if __name__ == "__main__":
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, "w", encoding="utf-8") as f:
            f.write("2024-01-01 12:00:00 INFO User 42 logged in\n")
            f.write("2024-01-01 12:05:00 ERROR Database timeout\n")
            f.write("2024-01-01 12:05:05 ERROR Database timeout\n")
            f.write("2024-01-01 12:08:00 INFO API /users/profile took 250ms\n")
            f.write("2024-01-01 12:09:00 WARN Memory usage at 87%\n")
            f.write("2024-01-01 12:10:00 INFO User 42 logged out\n")
    run_pipeline()
