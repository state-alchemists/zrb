"""
Log Processing Pipeline
Extracts metrics from server logs, loads them into a database, and generates an HTML report.
"""
import datetime
import os
import re
import sqlite3
from typing import Dict, List, Tuple

# Configuration using environment variables
DB_PATH = os.getenv("DB_PATH", "metrics.db")
LOG_FILE = os.getenv("LOG_FILE", "server.log")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_USER = os.getenv("DB_USER", "admin")
DB_PASS = os.getenv("DB_PASS", "password123")


def extract_logs(log_file: str) -> List[Dict[str, str]]:
    """
    Reads the log file and parses lines into structured data using regex.
    
    Args:
        log_file: Path to the log file.
        
    Returns:
        A list of dictionaries, each containing parsed log data ('date', 'time', 'level', 'message', 'dt').
    """
    logs = []
    if not os.path.exists(log_file):
        return logs
        
    log_pattern = re.compile(
        r"^(?P<date>\d{4}-\d{2}-\d{2})\s+(?P<time>\d{2}:\d{2}:\d{2})\s+(?P<level>\w+)\s+(?P<message>.*)$"
    )
    
    with open(log_file, "r") as f:
        for line in f:
            match = log_pattern.match(line.strip())
            if match:
                log_data = match.groupdict()
                log_data["dt"] = f"{log_data['date']} {log_data['time']}"
                logs.append(log_data)
                
    return logs


def transform_logs(logs: List[Dict[str, str]]) -> Tuple[Dict[str, int], Dict[str, float], int]:
    """
    Transforms parsed logs into aggregated metrics.
    
    Args:
        logs: A list of parsed log dictionaries.
        
    Returns:
        A tuple containing:
        - error_counts: Dictionary mapping error messages to their occurrence count.
        - api_latencies: Dictionary mapping endpoints to their average latency in ms.
        - active_sessions_count: Number of currently active user sessions.
    """
    error_counts: Dict[str, int] = {}
    endpoint_stats: Dict[str, List[int]] = {}
    sessions: Dict[str, str] = {}
    
    user_pattern = re.compile(r"^User\s+(?P<uid>\S+)\s+(?P<action>.*)$")
    api_pattern = re.compile(r"^API\s+(?P<endpoint>\S+)\s+took\s+(?P<duration>\d+)ms$")
    
    for log in logs:
        level = log["level"]
        msg = log["message"]
        dt = log["dt"]
        
        if level == "ERROR":
            error_counts[msg] = error_counts.get(msg, 0) + 1
            
        elif level == "INFO":
            user_match = user_pattern.match(msg)
            if user_match:
                uid = user_match.group("uid")
                action = user_match.group("action")
                if "logged in" in action:
                    sessions[uid] = dt
                elif "logged out" in action and uid in sessions:
                    del sessions[uid]
                continue
                
            api_match = api_pattern.match(msg)
            if api_match:
                endpoint = api_match.group("endpoint")
                duration = int(api_match.group("duration"))
                endpoint_stats.setdefault(endpoint, []).append(duration)
                
    api_latencies: Dict[str, float] = {}
    for ep, times in endpoint_stats.items():
        api_latencies[ep] = sum(times) / len(times)
        
    return error_counts, api_latencies, len(sessions)


def load_metrics_to_db(db_path: str, error_counts: Dict[str, int], api_latencies: Dict[str, float]) -> None:
    """
    Saves aggregated metrics to the SQLite database using parameterized queries.
    
    Args:
        db_path: Path to the SQLite database file.
        error_counts: Dictionary mapping error messages to their occurrence count.
        api_latencies: Dictionary mapping endpoints to their average latency in ms.
    """
    print(f"Connecting to {DB_HOST}:{DB_PORT} as {DB_USER}...")
    
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS errors (dt TEXT, message TEXT, count INTEGER)")
    c.execute("CREATE TABLE IF NOT EXISTS api_metrics (dt TEXT, endpoint TEXT, avg_ms REAL)")
    
    now = str(datetime.datetime.now())
    
    for msg, count in error_counts.items():
        c.execute("INSERT INTO errors VALUES (?, ?, ?)", (now, msg, count))
        
    for ep, avg in api_latencies.items():
        c.execute("INSERT INTO api_metrics VALUES (?, ?, ?)", (now, ep, avg))
        
    conn.commit()
    conn.close()


def generate_html_report(error_counts: Dict[str, int], api_latencies: Dict[str, float], active_sessions_count: int) -> None:
    """
    Generates an HTML report summarizing the system metrics.
    
    Args:
        error_counts: Dictionary mapping error messages to their occurrence count.
        api_latencies: Dictionary mapping endpoints to their average latency in ms.
        active_sessions_count: Number of currently active user sessions.
    """
    out = "<html>\n<head><title>System Report</title></head>\n<body>\n"
    out += "<h1>Error Summary</h1>\n<ul>\n"
    for err_msg, count in error_counts.items():
        out += f"<li><b>{err_msg}</b>: {count} occurrences</li>\n"
    out += "</ul>\n"

    out += "<h2>API Latency</h2>\n<table border='1'>\n"
    out += "<tr><th>Endpoint</th><th>Avg (ms)</th></tr>\n"
    for ep, avg in api_latencies.items():
        out += f"<tr><td>{ep}</td><td>{round(avg, 1)}</td></tr>\n"
    out += "</table>\n"

    out += "<h2>Active Sessions</h2>\n"
    out += f"<p>{active_sessions_count} user(s) currently active</p>\n"
    out += "</body>\n</html>"

    with open("report.html", "w") as f:
        f.write(out)


def run_pipeline() -> None:
    """Runs the ETL pipeline to process logs, update the database, and generate a report."""
    logs = extract_logs(LOG_FILE)
    error_counts, api_latencies, active_sessions_count = transform_logs(logs)
    load_metrics_to_db(DB_PATH, error_counts, api_latencies)
    generate_html_report(error_counts, api_latencies, active_sessions_count)
    print(f"Job finished at {datetime.datetime.now()}")


if __name__ == "__main__":
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, "w") as f:
            f.write("2024-01-01 12:00:00 INFO User 42 logged in\n")
            f.write("2024-01-01 12:05:00 ERROR Database timeout\n")
            f.write("2024-01-01 12:05:05 ERROR Database timeout\n")
            f.write("2024-01-01 12:08:00 INFO API /users/profile took 250ms\n")
            f.write("2024-01-01 12:09:00 WARN Memory usage at 87%\n")
            f.write("2024-01-01 12:10:00 INFO User 42 logged out\n")
    run_pipeline()
