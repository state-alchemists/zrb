import datetime
import os
import sqlite3
import re
from typing import List, Dict, Tuple, Any

DB_PATH = os.environ.get("DB_PATH", "metrics.db")
LOG_FILE = os.environ.get("LOG_FILE", "server.log")
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = int(os.environ.get("DB_PORT", "5432"))
DB_USER = os.environ.get("DB_USER", "admin")
DB_PASS = os.environ.get("DB_PASS", "password123")

LOG_PATTERN = re.compile(r"^(?P<date>\d{4}-\d{2}-\d{2})\s+(?P<time>\d{2}:\d{2}:\d{2})\s+(?P<level>[A-Z]+)\s+(?P<message>.*)$")
USER_PATTERN = re.compile(r"^User (?P<uid>\d+) (?P<action>.*)$")
API_PATTERN = re.compile(r"^API (?P<endpoint>\S+) took (?P<ms>\d+)ms$")

def extract_logs(log_file: str) -> List[Dict[str, Any]]:
    """Extracts and parses log entries from the log file.
    
    Args:
        log_file: Path to the log file.
        
    Returns:
        List of parsed log dictionaries.
    """
    logs = []
    if not os.path.exists(log_file):
        return logs

    with open(log_file, "r") as f:
        for line in f:
            match = LOG_PATTERN.match(line.strip())
            if match:
                log_data = match.groupdict()
                logs.append(log_data)
    return logs

def transform_data(logs: List[Dict[str, Any]]) -> Tuple[Dict[str, int], Dict[str, float], int]:
    """Transforms raw log data into aggregated metrics.
    
    Args:
        logs: List of parsed log dictionaries.
        
    Returns:
        A tuple containing:
        - Dictionary of error message counts
        - Dictionary of API endpoint average latencies (ms)
        - Count of active sessions
    """
    error_counts: Dict[str, int] = {}
    sessions: Dict[str, str] = {}
    api_metrics: Dict[str, List[int]] = {}

    for log in logs:
        level = log["level"]
        msg = log["message"]
        dt = f"{log['date']} {log['time']}"

        if level == "ERROR":
            error_counts[msg] = error_counts.get(msg, 0) + 1
        
        elif level == "INFO":
            user_match = USER_PATTERN.match(msg)
            if user_match:
                uid = user_match.group("uid")
                action = user_match.group("action")
                if "logged in" in action:
                    sessions[uid] = dt
                elif "logged out" in action and uid in sessions:
                    sessions.pop(uid)
            
            api_match = API_PATTERN.match(msg)
            if api_match:
                endpoint = api_match.group("endpoint")
                ms = int(api_match.group("ms"))
                api_metrics.setdefault(endpoint, []).append(ms)

    avg_api_metrics: Dict[str, float] = {}
    for ep, times in api_metrics.items():
        avg_api_metrics[ep] = sum(times) / len(times)

    return error_counts, avg_api_metrics, len(sessions)

def load_data_to_db(db_path: str, error_counts: Dict[str, int], api_metrics: Dict[str, float]) -> None:
    """Loads aggregated metrics into the SQLite database.
    
    Args:
        db_path: Path to the SQLite database.
        error_counts: Dictionary of error message counts.
        api_metrics: Dictionary of API endpoint average latencies.
    """
    print(f"Connecting to {DB_HOST}:{DB_PORT} as {DB_USER}...")
    
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS errors (dt TEXT, message TEXT, count INTEGER)")
    c.execute("CREATE TABLE IF NOT EXISTS api_metrics (dt TEXT, endpoint TEXT, avg_ms REAL)")

    now = datetime.datetime.now().isoformat()

    for msg, count in error_counts.items():
        c.execute("INSERT INTO errors VALUES (?, ?, ?)", (now, msg, count))

    for ep, avg in api_metrics.items():
        c.execute("INSERT INTO api_metrics VALUES (?, ?, ?)", (now, ep, avg))

    conn.commit()
    conn.close()

def load_data_to_report(report_path: str, error_counts: Dict[str, int], api_metrics: Dict[str, float], active_sessions: int) -> None:
    """Generates an HTML report from the aggregated metrics.
    
    Args:
        report_path: Path to the output HTML file.
        error_counts: Dictionary of error message counts.
        api_metrics: Dictionary of API endpoint average latencies.
        active_sessions: Current number of active sessions.
    """
    out = "<html>\n<head><title>System Report</title></head>\n<body>\n"
    out += "<h1>Error Summary</h1>\n<ul>\n"
    for err_msg, count in error_counts.items():
        out += f"<li><b>{err_msg}</b>: {count} occurrences</li>\n"
    out += "</ul>\n"

    out += "<h2>API Latency</h2>\n<table border='1'>\n"
    out += "<tr><th>Endpoint</th><th>Avg (ms)</th></tr>\n"
    for ep, avg in api_metrics.items():
        out += f"<tr><td>{ep}</td><td>{round(avg, 1)}</td></tr>\n"
    out += "</table>\n"

    out += "<h2>Active Sessions</h2>\n"
    out += f"<p>{active_sessions} user(s) currently active</p>\n"
    out += "</body>\n</html>"

    with open(report_path, "w") as f:
        f.write(out)

def run_pipeline() -> None:
    """Runs the ETL pipeline."""
    logs = extract_logs(LOG_FILE)
    error_counts, api_metrics, active_sessions = transform_data(logs)
    load_data_to_db(DB_PATH, error_counts, api_metrics)
    load_data_to_report("report.html", error_counts, api_metrics, active_sessions)
    print("Job finished at " + str(datetime.datetime.now()))

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
