import datetime
import os
import re
import sqlite3
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional

# --- Configuration ---
# Default values provided for compatibility if ENV vars are missing
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
    user_id: Optional[str] = None
    action: Optional[str] = None
    endpoint: Optional[str] = None
    latency_ms: Optional[int] = None

def extract_logs(file_path: str) -> List[LogEntry]:
    """
    Parses the server log file using regex and extracts structured data.
    """
    entries = []
    # Patterns for different log types
    # 2024-01-01 12:00:00 INFO User 42 logged in
    user_pattern = re.compile(r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) (INFO) User (\d+) (.+)$')
    # 2024-01-01 12:08:00 INFO API /users/profile took 250ms
    api_pattern = re.compile(r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) (INFO) API ([^ ]+) took (\d+)ms$')
    # 2024-01-01 12:05:00 ERROR Database timeout
    generic_pattern = re.compile(r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) (ERROR|WARN) (.+)$')

    if not os.path.exists(file_path):
        return entries

    with open(file_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            user_match = user_pattern.match(line)
            if user_match:
                ts, lvl, uid, act = user_match.groups()
                entries.append(LogEntry(timestamp=ts, level=lvl, message=line, user_id=uid, action=act))
                continue

            api_match = api_pattern.match(line)
            if api_match:
                ts, lvl, ep, lat = api_match.groups()
                entries.append(LogEntry(timestamp=ts, level=lvl, message=line, endpoint=ep, latency_ms=int(lat)))
                continue

            gen_match = generic_pattern.match(line)
            if gen_match:
                ts, lvl, msg = gen_match.groups()
                entries.append(LogEntry(timestamp=ts, level=lvl, message=msg))
                continue
    
    return entries

def transform_logs(entries: List[LogEntry]) -> Tuple[Dict[str, int], Dict[str, List[int]], int]:
    """
    Transforms raw log entries into useful metrics.
    Returns: (error_counts, api_latencies, active_sessions_count)
    """
    error_counts: Dict[str, int] = {}
    api_latencies: Dict[str, List[int]] = {}
    active_sessions: set = set()

    for entry in entries:
        if entry.level == "ERROR":
            error_counts[entry.message] = error_counts.get(entry.message, 0) + 1
        
        elif entry.endpoint:
            api_latencies.setdefault(entry.endpoint, []).append(entry.latency_ms or 0)
            
        elif entry.user_id:
            if entry.action and "logged in" in entry.action:
                active_sessions.add(entry.user_id)
            elif entry.action and "logged out" in entry.action:
                active_sessions.discard(entry.user_id)

    return error_counts, api_latencies, len(active_sessions)

def load_metrics(error_counts: Dict[str, int], api_latencies: Dict[str, List[int]]) -> None:
    """
    Stores aggregated metrics into the SQLite database using parameterized queries.
    """
    print(f"Connecting to {DB_HOST}:{DB_PORT} as {DB_USER}...")
    
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE IF NOT EXISTS errors (dt TEXT, message TEXT, count INTEGER)")
        cursor.execute("CREATE TABLE IF NOT EXISTS api_metrics (dt TEXT, endpoint TEXT, avg_ms REAL)")

        now = datetime.datetime.now().isoformat()

        # Parameterized insertion for errors
        error_data = [(now, msg, count) for msg, count in error_counts.items()]
        cursor.executemany("INSERT INTO errors VALUES (?, ?, ?)", error_data)

        # Parameterized insertion for API metrics
        api_data = [(now, ep, sum(times)/len(times)) for ep, times in api_latencies.items()]
        cursor.executemany("INSERT INTO api_metrics VALUES (?, ?, ?)", api_data)
        
        conn.commit()

def generate_report(error_counts: Dict[str, int], api_latencies: Dict[str, List[int]], session_count: int) -> None:
    """
    Generates a HTML report from the processed metrics.
    """
    html = "<html>\n<head><title>System Report</title></head>\n<body>\n"
    
    html += "<h1>Error Summary</h1>\n<ul>\n"
    for msg, count in error_counts.items():
        html += f"<li><b>{msg}</b>: {count} occurrences</li>\n"
    html += "</ul>\n"

    html += "<h2>API Latency</h2>\n<table border='1'>\n"
    html += "<tr><th>Endpoint</th><th>Avg (ms)</th></tr>\n"
    for ep, times in api_latencies.items():
        avg = sum(times) / len(times)
        html += f"<tr><td>{ep}</td><td>{round(avg, 1)}</td></tr>\n"
    html += "</table>\n"

    html += f"<h2>Active Sessions</h2>\n<p>{session_count} user(s) currently active</p>\n"
    html += "</body>\n</html>"

    with open("report.html", "w") as f:
        f.write(html)

def run_pipeline() -> None:
    """
    Orchestrates the ETL process for server logs.
    """
    # Extract
    entries = extract_logs(LOG_FILE)
    
    # Transform
    error_counts, api_latencies, session_count = transform_logs(entries)
    
    # Load
    load_metrics(error_counts, api_latencies)
    
    # Report
    generate_report(error_counts, api_latencies, session_count)
    
    print(f"Job finished at {datetime.datetime.now()}")

if __name__ == "__main__":
    # Generate sample log if it doesn't exist for local verification
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, "w") as f:
            f.write("2024-01-01 12:00:00 INFO User 42 logged in\n")
            f.write("2024-01-01 12:05:00 ERROR Database timeout\n")
            f.write("2024-01-01 12:05:05 ERROR Database timeout\n")
            f.write("2024-01-01 12:08:00 INFO API /users/profile took 250ms\n")
            f.write("2024-01-01 12:09:00 WARN Memory usage at 87%\n")
            f.write("2024-01-01 12:10:00 INFO User 42 logged out\n")
            
    run_pipeline()
