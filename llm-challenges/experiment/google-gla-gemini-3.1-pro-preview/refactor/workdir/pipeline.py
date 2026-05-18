import datetime
import os
import sqlite3
import re
from typing import Dict, List, Tuple, Any

DB_PATH = os.environ.get("DB_PATH", "metrics.db")
LOG_FILE = os.environ.get("LOG_FILE", "server.log")
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = os.environ.get("DB_PORT", "5432")
DB_USER = os.environ.get("DB_USER", "admin")
DB_PASS = os.environ.get("DB_PASS", "password123")

LOG_PATTERN = re.compile(r"^(?P<date>\d{4}-\d{2}-\d{2})\s+(?P<time>\d{2}:\d{2}:\d{2})\s+(?P<level>\w+)\s+(?P<message>.*)$")
USER_PATTERN = re.compile(r"^User (?P<uid>\S+) (?P<action>.*)$")
API_PATTERN = re.compile(r"^API (?P<endpoint>\S+) took (?P<dur>\d+)ms$")

def extract_logs(file_path: str) -> List[Dict[str, str]]:
    """
    Extract log lines from the given file.
    
    Args:
        file_path: Path to the log file.
        
    Returns:
        List of dictionaries containing parsed log data.
    """
    logs = []
    if not os.path.exists(file_path):
        return logs
    
    with open(file_path, "r") as f:
        for line in f:
            match = LOG_PATTERN.match(line.strip())
            if match:
                logs.append(match.groupdict())
    return logs

def transform_logs(logs: List[Dict[str, str]]) -> Tuple[Dict[str, int], Dict[str, float], int]:
    """
    Transform raw log lines into aggregated metrics.
    
    Args:
        logs: List of parsed log dictionaries.
        
    Returns:
        Tuple containing error counts, average API latencies, and active session count.
    """
    error_counts: Dict[str, int] = {}
    sessions: Dict[str, str] = {}
    api_stats: Dict[str, List[int]] = {}
    
    for log in logs:
        level = log["level"]
        message = log["message"]
        dt = f"{log['date']} {log['time']}"
        
        if level == "ERROR":
            error_counts[message] = error_counts.get(message, 0) + 1
            
        elif level == "INFO":
            user_match = USER_PATTERN.match(message)
            if user_match:
                uid = user_match.group("uid")
                action = user_match.group("action")
                if "logged in" in action:
                    sessions[uid] = dt
                elif "logged out" in action and uid in sessions:
                    sessions.pop(uid)
                continue
            
            api_match = API_PATTERN.match(message)
            if api_match:
                endpoint = api_match.group("endpoint")
                dur = int(api_match.group("dur"))
                api_stats.setdefault(endpoint, []).append(dur)
    
    avg_api_latency: Dict[str, float] = {}
    for ep, times in api_stats.items():
        avg_api_latency[ep] = sum(times) / len(times)
        
    return error_counts, avg_api_latency, len(sessions)

def load_to_db(db_path: str, error_counts: Dict[str, int], avg_api_latency: Dict[str, float]) -> None:
    """
    Load transformed metrics into the SQLite database securely using parameterized queries.
    
    Args:
        db_path: Path to the SQLite database file.
        error_counts: Dictionary of error messages and their counts.
        avg_api_latency: Dictionary of API endpoints and their average latencies.
    """
    print(f"Connecting to {DB_HOST}:{DB_PORT} as {DB_USER}...")
    
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS errors (dt TEXT, message TEXT, count INTEGER)")
    c.execute("CREATE TABLE IF NOT EXISTS api_metrics (dt TEXT, endpoint TEXT, avg_ms REAL)")
    
    now_str = str(datetime.datetime.now())
    
    for msg, count in error_counts.items():
        c.execute(
            "INSERT INTO errors (dt, message, count) VALUES (?, ?, ?)",
            (now_str, msg, count)
        )
        
    for ep, avg in avg_api_latency.items():
        c.execute(
            "INSERT INTO api_metrics (dt, endpoint, avg_ms) VALUES (?, ?, ?)",
            (now_str, ep, avg)
        )
        
    conn.commit()
    conn.close()

def generate_report(error_counts: Dict[str, int], avg_api_latency: Dict[str, float], active_sessions: int, output_file: str = "report.html") -> None:
    """
    Generate an HTML report with the aggregated metrics.
    
    Args:
        error_counts: Dictionary of error messages and their counts.
        avg_api_latency: Dictionary of API endpoints and their average latencies.
        active_sessions: Number of currently active sessions.
        output_file: Path to the output HTML report file.
    """
    out = "<html>\n<head><title>System Report</title></head>\n<body>\n"
    out += "<h1>Error Summary</h1>\n<ul>\n"
    for err_msg, count in error_counts.items():
        out += f"<li><b>{err_msg}</b>: {count} occurrences</li>\n"
    out += "</ul>\n"
    
    out += "<h2>API Latency</h2>\n<table border='1'>\n"
    out += "<tr><th>Endpoint</th><th>Avg (ms)</th></tr>\n"
    for ep, avg in avg_api_latency.items():
        out += f"<tr><td>{ep}</td><td>{round(avg, 1)}</td></tr>\n"
    out += "</table>\n"
    
    out += "<h2>Active Sessions</h2>\n"
    out += f"<p>{active_sessions} user(s) currently active</p>\n"
    out += "</body>\n</html>"
    
    with open(output_file, "w") as f:
        f.write(out)

def proc_data() -> None:
    """Run the ETL pipeline to process server logs and generate a report."""
    logs = extract_logs(LOG_FILE)
    error_counts, avg_api_latency, active_sessions = transform_logs(logs)
    load_to_db(DB_PATH, error_counts, avg_api_latency)
    generate_report(error_counts, avg_api_latency, active_sessions)
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
    proc_data()
