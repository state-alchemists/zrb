import datetime
import os
import re
import sqlite3
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass

# --- Configuration ---
# Use environment variables with defaults for local development
DB_PATH = os.getenv("DB_PATH", "metrics.db")
LOG_FILE = os.getenv("LOG_FILE", "server.log")
# These were hardcoded in old script and not used by sqlite3, but kept for parity/env support
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_USER = os.getenv("DB_USER", "admin")
DB_PASS = os.getenv("DB_PASS", "password123")

# --- Log Patterns ---
# Example log line: 2024-01-01 12:00:00 INFO User 42 logged in
# Example log line: 2024-01-01 12:05:00 ERROR Database timeout
# Example log line: 2024-01-01 12:08:00 INFO API /users/profile took 250ms
LOG_PATTERN = re.compile(r"(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s+(?P<level>INFO|ERROR|WARN)\s+(?P<message>.*)")
USER_PATTERN = re.compile(r"User (?P<uid>\S+) (?P<action>.*)")
API_PATTERN = re.compile(r"API (?P<endpoint>\S+)(?: took (?P<duration>\d+)ms)?")

@dataclass
class LogEntry:
    timestamp: str
    level: str
    message: str

def extract_logs(file_path: str) -> List[LogEntry]:
    """
    Reads the log file and extracts structured LogEntry objects using regex.
    """
    entries = []
    if not os.path.exists(file_path):
        return entries

    with open(file_path, "r") as f:
        for line in f:
            match = LOG_PATTERN.match(line.strip())
            if match:
                entries.append(LogEntry(**match.groupdict()))
    return entries

def transform_logs(entries: List[LogEntry]) -> Tuple[Dict[str, int], Dict[str, List[int]], int]:
    """
    Processes raw log entries into aggregated statistics.
    
    Returns:
        - error_counts: Map of error message to frequency
        - api_latencies: Map of endpoint to list of durations
        - active_sessions: Number of currently active users
    """
    error_counts: Dict[str, int] = {}
    api_latencies: Dict[str, List[int]] = {}
    active_sessions: set = set()

    for entry in entries:
        msg = entry.message
        if entry.level == "ERROR":
            error_counts[msg] = error_counts.get(msg, 0) + 1
        
        elif entry.level == "INFO":
            # Check for user activity
            user_match = USER_PATTERN.match(msg)
            if user_match:
                uid = user_match.group("uid")
                action = user_match.group("action")
                if "logged in" in action:
                    active_sessions.add(uid)
                elif "logged out" in action:
                    active_sessions.discard(uid)
                continue

            # Check for API activity
            api_match = API_PATTERN.match(msg)
            if api_match:
                endpoint = api_match.group("endpoint")
                duration = int(api_match.group("duration") or 0)
                api_latencies.setdefault(endpoint, []).append(duration)
        
        elif entry.level == "WARN":
            # Original script didn't aggregate WARNs into the database, 
            # they were added to d_list but not the summary. 
            # Keeping behavior consistent.
            pass

    return error_counts, api_latencies, len(active_sessions)

def load_metrics(error_counts: Dict[str, int], api_latencies: Dict[str, List[int]]) -> None:
    """
    Persists aggregated metrics to the SQLite database using parameterized queries.
    """
    now = datetime.datetime.now().isoformat()
    
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE IF NOT EXISTS errors (dt TEXT, message TEXT, count INTEGER)")
        cursor.execute("CREATE TABLE IF NOT EXISTS api_metrics (dt TEXT, endpoint TEXT, avg_ms REAL)")

        # Parameterized insert for errors
        error_data = [(now, msg, count) for msg, count in error_counts.items()]
        cursor.executemany("INSERT INTO errors (dt, message, count) VALUES (?, ?, ?)", error_data)

        # Average latencies and parameterized insert
        api_data = [
            (now, ep, sum(times) / len(times)) 
            for ep, times in api_latencies.items() if times
        ]
        cursor.executemany("INSERT INTO api_metrics (dt, endpoint, avg_ms) VALUES (?, ?, ?)", api_data)
        
        conn.commit()

def generate_report(error_counts: Dict[str, int], api_latencies: Dict[str, List[int]], session_count: int) -> None:
    """
    Generates the final report.html file.
    """
    html = ["<html>", "<head><title>System Report</title></head>", "<body>"]
    
    html.append("<h1>Error Summary</h1>")
    html.append("<ul>")
    for msg, count in error_counts.items():
        html.append(f"<li><b>{msg}</b>: {count} occurrences</li>")
    html.append("</ul>")

    html.append("<h2>API Latency</h2>")
    html.append("<table border='1'>")
    html.append("<tr><th>Endpoint</th><th>Avg (ms)</th></tr>")
    for ep, times in api_latencies.items():
        avg = sum(times) / len(times) if times else 0
        html.append(f"<tr><td>{ep}</td><td>{round(avg, 1)}</td></tr>")
    html.append("</table>")

    html.append("<h2>Active Sessions</h2>")
    html.append(f"<p>{session_count} user(s) currently active</p>")
    
    html.append("</body>")
    html.append("</html>")

    with open("report.html", "w") as f:
        f.write("\n".join(html))

def run_pipeline() -> None:
    """
    Orchestrates the ETL pipeline.
    """
    print(f"Connecting to {DB_HOST}:{DB_PORT} as {DB_USER}...")
    
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
    # Create dummy log for initial run if missing (maintaining original behavior)
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, "w") as f:
            f.write("2024-01-01 12:00:00 INFO User 42 logged in\n")
            f.write("2024-01-01 12:05:00 ERROR Database timeout\n")
            f.write("2024-01-01 12:05:05 ERROR Database timeout\n")
            f.write("2024-01-01 12:08:00 INFO API /users/profile took 250ms\n")
            f.write("2024-01-01 12:09:00 WARN Memory usage at 87%\n")
            f.write("2024-01-01 12:10:00 INFO User 42 logged out\n")
    
    run_pipeline()
