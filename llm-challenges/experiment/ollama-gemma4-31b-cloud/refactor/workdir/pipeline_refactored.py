import datetime
import os
import re
import sqlite3
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple

# Configuration via Environment Variables
DB_PATH = os.getenv("DB_PATH", "metrics.db")
LOG_FILE = os.getenv("LOG_FILE", "server.log")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_USER = os.getenv("DB_USER", "admin")
DB_PASS = os.getenv("DB_PASS", "password123")

@dataclass
class LogEntry:
    timestamp: str
    level: str
    message: str
    type: str  # 'ERR', 'USR', 'API', 'WARN'
    metadata: Dict[str, Any] = field(default_factory=dict)

def extract_logs(file_path: str) -> List[LogEntry]:
    """
    Extracts and parses logs from the specified file using regex.
    
    Args:
        file_path: Path to the log file.
        
    Returns:
        List of parsed LogEntry objects.
    """
    entries = []
    # Regex to match: YYYY-MM-DD HH:MM:SS LEVEL Message
    # Group 1: Timestamp, Group 2: Level, Group 3: Message
    log_pattern = re.compile(r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) (\w+) (.*)$')
    
    if not os.path.exists(file_path):
        return entries

    with open(file_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
                
            match = log_pattern.match(line)
            if not match:
                continue
                
            dt, lvl, msg = match.groups()
            
            if lvl == "ERROR":
                entries.append(LogEntry(dt, lvl, msg, 'ERR'))
            elif lvl == "WARN":
                entries.append(LogEntry(dt, lvl, msg, 'WARN'))
            elif lvl == "INFO":
                if "User " in msg:
                    # Match "User <id> <action>"
                    user_match = re.search(r'User (\w+) (.*)', msg)
                    if user_match:
                        uid, action = user_match.groups()
                        entries.append(LogEntry(dt, lvl, msg, 'USR', {"user_id": uid, "action": action}))
                elif "API " in msg:
                    # Match "API <endpoint> took <ms>ms"
                    api_match = re.search(r'API ([/\w\.]+) took (\d+)ms', msg)
                    if api_match:
                        endpoint, duration = api_match.groups()
                        entries.append(LogEntry(dt, lvl, msg, 'API', {"endpoint": endpoint, "duration": int(duration)}))
    return entries

def transform_data(entries: List[LogEntry]) -> Tuple[Dict[str, int], Dict[str, List[int]], int]:
    """
    Transforms raw log entries into aggregated metrics.
    
    Args:
        entries: List of parsed LogEntry objects.
        
    Returns:
        A tuple containing:
        - Error summary (message -> count)
        - API latency (endpoint -> list of durations)
        - Active session count
    """
    error_summary = {}
    api_metrics = {}
    active_sessions = set()

    for entry in entries:
        if entry.type == 'ERR':
            msg = entry.message
            error_summary[msg] = error_summary.get(msg, 0) + 1
        elif entry.type == 'API':
            ep = entry.metadata['endpoint']
            dur = entry.metadata['duration']
            api_metrics.setdefault(ep, []).append(dur)
        elif entry.type == 'USR':
            uid = entry.metadata['user_id']
            action = entry.metadata['action']
            if "logged in" in action:
                active_sessions.add(uid)
            elif "logged out" in action:
                active_sessions.discard(uid)

    return error_summary, api_metrics, len(active_sessions)

def load_to_db(error_summary: Dict[str, int], api_metrics: Dict[str, List[int]]) -> None:
    """
    Loads aggregated metrics into the SQLite database using parameterized queries.
    """
    print(f"Connecting to {DB_HOST}:{DB_PORT} as {DB_USER}...")
    
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("CREATE TABLE IF NOT EXISTS errors (dt TEXT, message TEXT, count INTEGER)")
        c.execute("CREATE TABLE IF NOT EXISTS api_metrics (dt TEXT, endpoint TEXT, avg_ms REAL)")

        now = datetime.datetime.now().isoformat()
        
        for msg, count in error_summary.items():
            c.execute("INSERT INTO errors VALUES (?, ?, ?)", (now, msg, count))

        for ep, times in api_metrics.items():
            avg = sum(times) / len(times) if times else 0
            c.execute("INSERT INTO api_metrics VALUES (?, ?, ?)", (now, ep, avg))
        
        conn.commit()

def generate_report(error_summary: Dict[str, int], api_metrics: Dict[str, List[int]], active_count: int) -> None:
    """
    Generates the HTML report file.
    """
    out = "<html>\n<head><title>System Report</title></head>\n<body>\n"
    out += "<h1>Error Summary</h1>\n<ul>\n"
    for err_msg, count in error_summary.items():
        out += f"<li><b>{err_msg}</b>: {count} occurrences</li>\n"
    out += "</ul>\n"

    out += "<h2>API Latency</h2>\n<table border='1'>\n"
    out += "<tr><th>Endpoint</th><th>Avg (ms)</th></tr>\n"
    for ep, times in api_metrics.items():
        avg = sum(times) / len(times) if times else 0
        out += f"<tr><td>{ep}</td><td>{round(avg, 1)}</td></tr>\n"
    out += "</table>\n"

    out += f"<h2>Active Sessions</h2>\n<p>{active_count} user(s) currently active</p>\n"
    out += "</body>\n</html>"

    with open("report.html", "w") as f:
        f.write(out)

def run_pipeline() -> None:
    """
    Main execution flow: Extract -> Transform -> Load -> Report.
    """
    # Extract
    entries = extract_logs(LOG_FILE)
    
    # Transform
    error_summary, api_metrics, active_count = transform_data(entries)
    
    # Load
    load_to_db(error_summary, api_metrics)
    
    # Report
    generate_report(error_summary, api_metrics, active_count)
    
    print(f"Job finished at {datetime.datetime.now()}")

if __name__ == "__main__":
    # Mock data creation for testing purposes (matching original script)
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, "w") as f:
            f.write("2024-01-01 12:00:00 INFO User 42 logged in\n")
            f.write("2024-01-01 12:05:00 ERROR Database timeout\n")
            f.write("2024-01-01 12:05:05 ERROR Database timeout\n")
            f.write("2024-01-01 12:08:00 INFO API /users/profile took 250ms\n")
            f.write("2024-01-01 12:09:00 WARN Memory usage at 87%\n")
            f.write("2024-01-01 12:10:00 INFO User 42 logged out\n")
            
    run_pipeline()
