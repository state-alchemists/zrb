import datetime
import os
import re
import sqlite3
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

# Configuration via Environment Variables
DB_PATH = os.getenv("DB_PATH", "metrics.db")
LOG_FILE = os.getenv("LOG_FILE", "server.log")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_USER = os.getenv("DB_USER", "admin")
DB_PASS = os.getenv("DB_PASS", "password123")

@dataclass
class LogEntry:
    timestamp: str
    level: str
    message: str
    user_id: Optional[str] = None
    action: Optional[str] = None
    endpoint: Optional[str] = None
    latency_ms: Optional[int] = None

def parse_logs(file_path: str) -> Tuple[List[LogEntry], Dict[str, str]]:
    """
    Parses the server log file using regex to extract structured log entries.
    
    Args:
        file_path: Path to the log file.
        
    Returns:
        A tuple containing a list of LogEntry objects and a dictionary of active sessions.
    """
    entries: List[LogEntry] = []
    sessions: Dict[str, str] = {}
    
    # Regex Patterns
    # Format: YYYY-MM-DD HH:MM:SS LEVEL ...
    base_pattern = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) (\w+) (.+)$")
    user_pattern = re.compile(r"User (\w+) (.+)$")
    api_pattern = re.compile(r"API ([/\w\s\d._-]+) took (\d+)ms")

    if not os.path.exists(file_path):
        return entries, sessions

    with open(file_path, "r") as f:
        for line in f:
            match = base_pattern.match(line.strip())
            if not match:
                continue
            
            dt, lvl, content = match.groups()
            
            if lvl == "ERROR":
                entries.append(LogEntry(timestamp=dt, level=lvl, message=content))
            
            elif lvl == "WARN":
                entries.append(LogEntry(timestamp=dt, level=lvl, message=content))
            
            elif lvl == "INFO":
                if "User" in content:
                    u_match = user_pattern.search(content)
                    if u_match:
                        uid, action = u_match.groups()
                        if "logged in" in action:
                            sessions[uid] = dt
                        elif "logged out" in action:
                            sessions.pop(uid, None)
                        entries.append(LogEntry(timestamp=dt, level=lvl, message=content, user_id=uid, action=action))
                
                elif "API" in content:
                    a_match = api_pattern.search(content)
                    if a_match:
                        endpoint, latency = a_match.groups()
                        entries.append(LogEntry(timestamp=dt, level=lvl, message=content, endpoint=endpoint, latency_ms=int(latency)))
                        
    return entries, sessions

def transform_metrics(entries: List[LogEntry]) -> Tuple[Dict[str, int], Dict[str, List[int]]]:
    """
    Aggregates logs into error counts and API latency distributions.
    
    Args:
        entries: List of structured log entries.
        
    Returns:
        A tuple of (error_summary, endpoint_latencies).
    """
    error_summary: Dict[str, int] = {}
    endpoint_latencies: Dict[str, List[int]] = {}
    
    for entry in entries:
        if entry.level == "ERROR":
            error_summary[entry.message] = error_summary.get(entry.message, 0) + 1
        elif entry.endpoint and entry.latency_ms is not None:
            endpoint_latencies.setdefault(entry.endpoint, []).append(entry.latency_ms)
            
    return error_summary, endpoint_latencies

def load_to_db(errors: Dict[str, int], api_metrics: Dict[str, List[int]]) -> None:
    """
    Persists aggregated metrics to the SQLite database using parameterized queries.
    
    Args:
        errors: Dictionary of error messages and their counts.
        api_metrics: Dictionary of endpoints and their latency lists.
    """
    print(f"Connecting to {DB_HOST}:{DB_PORT} as {DB_USER}...")
    
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("CREATE TABLE IF NOT EXISTS errors (dt TEXT, message TEXT, count INTEGER)")
        c.execute("CREATE TABLE IF NOT EXISTS api_metrics (dt TEXT, endpoint TEXT, avg_ms REAL)")
        
        now = datetime.datetime.now().isoformat()
        
        # Parameterized inserts for errors
        error_data = [(now, msg, count) for msg, count in errors.items()]
        c.executemany("INSERT INTO errors VALUES (?, ?, ?)", error_data)
        
        # Parameterized inserts for API metrics
        api_data = []
        for ep, latencies in api_metrics.items():
            avg = sum(latencies) / len(latencies) if latencies else 0
            api_data.append((now, ep, avg))
        c.executemany("INSERT INTO api_metrics VALUES (?, ?, ?)", api_data)
        
        conn.commit()

def generate_report(errors: Dict[str, int], api_metrics: Dict[str, List[int]], active_session_count: int) -> None:
    """
    Generates the report.html file with a summary of system health.
    """
    html = "<html>\n<head><title>System Report</title></head>\n<body>\n"
    html += "<h1>Error Summary</h1>\n<ul>\n"
    for msg, count in errors.items():
        html += f"<li><b>{msg}</b>: {count} occurrences</li>\n"
    html += "</ul>\n"
    
    html += "<h2>API Latency</h2>\n<table border='1'>\n"
    html += "<tr><th>Endpoint</th><th>Avg (ms)</th></tr>\n"
    for ep, latencies in api_metrics.items():
        avg = sum(latencies) / len(latencies) if latencies else 0
        html += f"<tr><td>{ep}</td><td>{round(avg, 1)}</td></tr>\n"
    html += "</table>\n"
    
    html += f"<h2>Active Sessions</h2>\n<p>{active_session_count} user(s) currently active</p>\n"
    html += "</body>\n</html>"
    
    with open("report.html", "w") as f:
        f.write(html)

def run_pipeline() -> None:
    """
    Main orchestrator for the Extract-Transform-Load pipeline.
    """
    # EXTRACT
    entries, sessions = parse_logs(LOG_FILE)
    
    # TRANSFORM
    error_summary, endpoint_latencies = transform_metrics(entries)
    
    # LOAD
    load_to_db(error_summary, endpoint_latencies)
    
    # REPORT
    generate_report(error_summary, endpoint_latencies, len(sessions))
    
    print(f"Job finished at {datetime.datetime.now()}")

if __name__ == "__main__":
    # Maintain original seed data creation for consistency in testing
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, "w") as f:
            f.write("2024-01-01 12:00:00 INFO User 42 logged in\n")
            f.write("2024-01-01 12:05:00 ERROR Database timeout\n")
            f.write("2024-01-01 12:05:05 ERROR Database timeout\n")
            f.write("2024-01-01 12:08:00 INFO API /users/profile took 250ms\n")
            f.write("2024-01-01 12:09:00 WARN Memory usage at 87%\n")
            f.write("2024-01-01 12:10:00 INFO User 42 logged out\n")
            
    run_pipeline()
