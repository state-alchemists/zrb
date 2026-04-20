import datetime
import os
import re
import sqlite3
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

# Configuration from environment variables
DB_PATH = os.getenv("DB_PATH", "metrics.db")
LOG_FILE = os.getenv("LOG_FILE", "server.log")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_USER = os.getenv("DB_USER", "admin")
DB_PASS = os.getenv("DB_PASS", "password123")

@dataclass
class LogEntry:
    dt: str
    level: str
    message: str
    uid: Optional[str] = None
    action: Optional[str] = None
    endpoint: Optional[str] = None
    latency_ms: Optional[int] = None

def extract_logs(file_path: str) -> List[LogEntry]:
    """
    Reads the log file and parses each line using regex.
    """
    entries = []
    if not os.path.exists(file_path):
        return entries

    # Regex patterns
    # Example: 2024-01-01 12:00:00 INFO User 42 logged in
    base_pattern = re.compile(r"^(?P<dt>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) (?P<lvl>\S+) (?P<msg>.*)$")
    user_pattern = re.compile(r"User (?P<uid>\S+) (?P<action>.*)")
    api_pattern = re.compile(r"API (?P<endpoint>\S+) took (?P<ms>\d+)ms")

    with open(file_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            
            match = base_pattern.match(line)
            if not match:
                continue

            dt = match.group("dt")
            lvl = match.group("lvl")
            msg = match.group("msg")

            entry = LogEntry(dt=dt, level=lvl, message=msg)

            if lvl == "INFO":
                user_match = user_pattern.match(msg)
                if user_match:
                    entry.uid = user_match.group("uid")
                    entry.action = user_match.group("action")
                
                api_match = api_pattern.match(msg)
                if api_match:
                    entry.endpoint = api_match.group("endpoint")
                    entry.latency_ms = int(api_match.group("ms"))
            
            entries.append(entry)
    
    return entries

def transform_metrics(entries: List[LogEntry]) -> Tuple[Dict[str, int], Dict[str, float], int]:
    """
    Processes log entries into summarized metrics.
    Returns: (error_counts, api_averages, active_session_count)
    """
    error_counts = {}
    api_latencies = {}
    sessions = {}

    for entry in entries:
        # Error Summary
        if entry.level == "ERROR":
            error_counts[entry.message] = error_counts.get(entry.message, 0) + 1
        
        # User Sessions
        if entry.uid and entry.action:
            if "logged in" in entry.action:
                sessions[entry.uid] = entry.dt
            elif "logged out" in entry.action and entry.uid in sessions:
                sessions.pop(entry.uid)
        
        # API Latency
        if entry.endpoint and entry.latency_ms is not None:
            api_latencies.setdefault(entry.endpoint, []).append(entry.latency_ms)

    api_averages = {
        ep: sum(latencies) / len(latencies)
        for ep, latencies in api_latencies.items()
    }

    return error_counts, api_averages, len(sessions)

def load_data(
    error_counts: Dict[str, int], 
    api_averages: Dict[str, float], 
    active_sessions: int,
    db_path: str
) -> None:
    """
    Saves metrics to the database using parameterized queries and generates the HTML report.
    """
    print(f"Connecting to {DB_HOST}:{DB_PORT} as {DB_USER}...")
    
    conn = sqlite3.connect(db_path)
    try:
        c = conn.cursor()
        c.execute("CREATE TABLE IF NOT EXISTS errors (dt TEXT, message TEXT, count INTEGER)")
        c.execute("CREATE TABLE IF NOT EXISTS api_metrics (dt TEXT, endpoint TEXT, avg_ms REAL)")

        now = str(datetime.datetime.now())

        # Insert errors
        for msg, count in error_counts.items():
            c.execute(
                "INSERT INTO errors (dt, message, count) VALUES (?, ?, ?)",
                (now, msg, count)
            )

        # Insert API metrics
        for ep, avg in api_averages.items():
            c.execute(
                "INSERT INTO api_metrics (dt, endpoint, avg_ms) VALUES (?, ?, ?)",
                (now, ep, avg)
            )

        conn.commit()
    finally:
        conn.close()

    # Generate HTML report
    report_content = f"""<html>
<head><title>System Report</title></head>
<body>
<h1>Error Summary</h1>
<ul>
{"".join(f"<li><b>{msg}</b>: {count} occurrences</li>\n" for msg, count in error_counts.items())}</ul>
<h2>API Latency</h2>
<table border='1'>
<tr><th>Endpoint</th><th>Avg (ms)</th></tr>
{"".join(f"<tr><td>{ep}</td><td>{round(avg, 1)}</td></tr>\n" for ep, avg in api_averages.items())}</table>
<h2>Active Sessions</h2>
<p>{active_sessions} user(s) currently active</p>
</body>
</html>"""

    with open("report.html", "w") as f:
        f.write(report_content)

    print(f"Job finished at {datetime.datetime.now()}")

def main():
    # Ensure log file exists for demo purposes, matching original script behavior
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, "w") as f:
            f.write("2024-01-01 12:00:00 INFO User 42 logged in\n")
            f.write("2024-01-01 12:05:00 ERROR Database timeout\n")
            f.write("2024-01-01 12:05:05 ERROR Database timeout\n")
            f.write("2024-01-01 12:08:00 INFO API /users/profile took 250ms\n")
            f.write("2024-01-01 12:09:00 WARN Memory usage at 87%\n")
            f.write("2024-01-01 12:10:00 INFO User 42 logged out\n")

    # ETL Pipeline
    entries = extract_logs(LOG_FILE)
    error_counts, api_averages, active_sessions = transform_metrics(entries)
    load_data(error_counts, api_averages, active_sessions, DB_PATH)

if __name__ == "__main__":
    main()
