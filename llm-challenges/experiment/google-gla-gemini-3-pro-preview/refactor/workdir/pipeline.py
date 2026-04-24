import datetime
import os
import sqlite3
import re
from typing import List, Dict, Any, Tuple

# Configuration via environment variables
DB_PATH = os.getenv("DB_PATH", "metrics.db")
LOG_FILE = os.getenv("LOG_FILE", "server.log")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_USER = os.getenv("DB_USER", "admin")
DB_PASS = os.getenv("DB_PASS", "password123")

LOG_PATTERN = re.compile(r"^(?P<dt>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s+(?P<level>\w+)\s+(?P<msg>.*)$")
USER_PATTERN = re.compile(r"^User (?P<uid>\S+) (?P<action>.*)$")
API_PATTERN = re.compile(r"^API (?P<endpoint>\S+) took (?P<ms>\d+)ms$")

def extract_logs(file_path: str) -> List[Dict[str, str]]:
    """
    Reads the log file and parses lines into structured dictionaries using regex.
    """
    extracted: List[Dict[str, str]] = []
    if not os.path.exists(file_path):
        return extracted
        
    with open(file_path, "r") as f:
        for line in f:
            match = LOG_PATTERN.match(line.strip())
            if match:
                extracted.append(match.groupdict())
    return extracted

def transform_data(raw_logs: List[Dict[str, str]]) -> Tuple[Dict[str, int], Dict[str, float], int]:
    """
    Transforms raw log entries into aggregated metrics:
    - error_counts: Count of each error message
    - api_latencies: Average latency per endpoint
    - active_sessions: Number of currently active users
    """
    error_counts: Dict[str, int] = {}
    endpoint_stats: Dict[str, List[int]] = {}
    sessions: Dict[str, str] = {}
    
    for log in raw_logs:
        lvl = log["level"]
        msg = log["msg"]
        dt = log["dt"]
        
        if lvl == "ERROR":
            error_counts[msg] = error_counts.get(msg, 0) + 1
            
        elif lvl == "INFO":
            user_match = USER_PATTERN.match(msg)
            if user_match:
                uid = user_match.group("uid")
                action = user_match.group("action")
                if "logged in" in action:
                    sessions[uid] = dt
                elif "logged out" in action and uid in sessions:
                    del sessions[uid]
                continue
                
            api_match = API_PATTERN.match(msg)
            if api_match:
                endpoint = api_match.group("endpoint")
                ms = int(api_match.group("ms"))
                endpoint_stats.setdefault(endpoint, []).append(ms)
                continue

    api_latencies: Dict[str, float] = {}
    for ep, times in endpoint_stats.items():
        if times:
            api_latencies[ep] = sum(times) / len(times)
            
    active_sessions = len(sessions)
    
    return error_counts, api_latencies, active_sessions

def load_data(db_path: str, error_counts: Dict[str, int], api_latencies: Dict[str, float]) -> None:
    """
    Loads aggregated metrics into the SQLite database using parameterized queries.
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
        
    for ep, avg in api_latencies.items():
        c.execute(
            "INSERT INTO api_metrics (dt, endpoint, avg_ms) VALUES (?, ?, ?)",
            (now_str, ep, avg)
        )
        
    conn.commit()
    conn.close()

def generate_report(error_counts: Dict[str, int], api_latencies: Dict[str, float], active_sessions: int, output_file: str = "report.html") -> None:
    """
    Generates an HTML report summarizing errors, API latencies, and active sessions.
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
    out += f"<p>{active_sessions} user(s) currently active</p>\n"
    
    out += "</body>\n</html>\n"

    with open(output_file, "w") as f:
        f.write(out)

def run_pipeline() -> None:
    """
    Executes the ETL pipeline: extract, transform, load, and report generation.
    """
    raw_logs = extract_logs(LOG_FILE)
    error_counts, api_latencies, active_sessions = transform_data(raw_logs)
    
    load_data(DB_PATH, error_counts, api_latencies)
    generate_report(error_counts, api_latencies, active_sessions)
    
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