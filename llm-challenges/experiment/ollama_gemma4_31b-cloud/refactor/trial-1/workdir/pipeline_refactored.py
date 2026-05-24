import datetime
import os
import re
import sqlite3
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple

# Configuration from environment variables
DB_PATH = os.getenv("ZRB_DB_PATH", "metrics.db")
LOG_FILE = os.getenv("ZRB_LOG_FILE", "server.log")
DB_HOST = os.getenv("ZRB_DB_HOST", "localhost")
DB_PORT = int(os.getenv("ZRB_DB_PORT", "5432"))
DB_USER = os.getenv("ZRB_DB_USER", "admin")
DB_PASS = os.getenv("ZRB_DB_PASS", "password123")

@dataclass
class LogEntry:
    timestamp: str
    level: str
    message: str
    user_id: Optional[str] = None
    action: Optional[str] = None
    endpoint: Optional[str] = None
    latency_ms: Optional[int] = None

# Regex patterns for log parsing
# Format: YYYY-MM-DD HH:MM:SS LEVEL MESSAGE
LOG_PATTERN = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) (\w+) (.+)$")
USER_PATTERN = re.compile(r"User (\w+) (logged in|logged out)")
API_PATTERN = re.compile(r"API ([/\w\s\.\-]+) took (\d+)ms")

def extract_logs(file_path: str) -> List[LogEntry]:
    """
    Reads the log file and parses lines into LogEntry objects using regex.
    
    Args:
        file_path: Path to the server log file.
    Returns:
        A list of structured LogEntry objects.
    """
    entries = []
    if not os.path.exists(file_path):
        return entries

    with open(file_path, "r") as f:
        for line in f:
            line = line.strip()
            match = LOG_PATTERN.match(line)
            if not match:
                continue

            ts, lvl, msg = match.groups()
            entry = LogEntry(timestamp=ts, level=lvl, message=msg)

            if lvl == "INFO":
                # Check for User activity
                user_match = USER_PATTERN.search(msg)
                if user_match:
                    entry.user_id, entry.action = user_match.groups()
                
                # Check for API calls
                api_match = API_PATTERN.search(msg)
                if api_match:
                    entry.endpoint, latency = api_match.groups()
                    entry.latency_ms = int(latency)

            entries.append(entry)
    return entries

def transform_metrics(entries: List[LogEntry]) -> Tuple[Dict[str, int], Dict[str, List[int]], int]:
    """
    Processes raw log entries to calculate error counts, API latencies, and active sessions.
    
    Args:
        entries: List of parsed log entries.
    Returns:
        A tuple containing:
        - error_counts: Map of error messages to their occurrences.
        - api_latencies: Map of endpoints to a list of latency measurements.
        - active_sessions: Count of users currently logged in.
    """
    error_counts: Dict[str, int] = {}
    api_latencies: Dict[str, List[int]] = {}
    active_users = set()

    for entry in entries:
        if entry.level == "ERROR":
            error_counts[entry.message] = error_counts.get(entry.message, 0) + 1
        
        elif entry.level == "INFO":
            if entry.user_id and entry.action:
                if entry.action == "logged in":
                    active_users.add(entry.user_id)
                elif entry.action == "logged out":
                    active_users.discard(entry.user_id)
            
            if entry.endpoint and entry.latency_ms is not None:
                api_latencies.setdefault(entry.endpoint, []).append(entry.latency_ms)

    return error_counts, api_latencies, len(active_users)

def load_to_db(error_counts: Dict[str, int], api_latencies: Dict[str, List[int]]) -> None:
    """
    Persists aggregated metrics into the SQLite database using parameterized queries.
    
    Args:
        error_counts: Aggregated error metrics.
        api_latencies: Aggregated API latency data.
    """
    print(f"Connecting to {DB_HOST}:{DB_PORT} as {DB_USER}...")
    
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE IF NOT EXISTS errors (dt TEXT, message TEXT, count INTEGER)")
        cursor.execute("CREATE TABLE IF NOT EXISTS api_metrics (dt TEXT, endpoint TEXT, avg_ms REAL)")

        now = datetime.datetime.now().isoformat()

        for msg, count in error_counts.items():
            cursor.execute("INSERT INTO errors VALUES (?, ?, ?)", (now, msg, count))

        for ep, times in api_latencies.items():
            avg = sum(times) / len(times) if times else 0
            cursor.execute("INSERT INTO api_metrics VALUES (?, ?, ?)", (now, ep, avg))
        
        conn.commit()

def generate_report(error_counts: Dict[str, int], api_latencies: Dict[str, List[int]], session_count: int, output_path: str = "report.html") -> None:
    """
    Generates an HTML report from calculated metrics.
    
    Args:
        error_counts: Map of error messages to occurrences.
        api_latencies: Map of endpoints to latency lists.
        session_count: Number of active sessions.
        output_path: Path to save the generated HTML file.
    """
    html = [
        "<html>",
        "<head><title>System Report</title></head>",
        "<body>",
        "<h1>Error Summary</h1>",
        "<ul>"
    ]
    
    for err_msg, count in error_counts.items():
        html.append(f"<li><b>{err_msg}</b>: {count} occurrences</li>")
    
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

    with open(output_path, "w") as f:
        f.write("\n".join(html))

def run_pipeline() -> None:
    """
    Main orchestration function for the logging pipeline.
    """
    # Extract
    entries = extract_logs(LOG_FILE)
    
    # Transform
    error_counts, api_latencies, session_count = transform_metrics(entries)
    
    # Load
    load_to_db(error_counts, api_latencies)
    
    # Report
    generate_report(error_counts, api_latencies, session_count)
    
    print(f"Job finished at {datetime.datetime.now()}")

if __name__ == "__main__":
    # Initial scaffolding for testability (as per original script)
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, "w") as f:
            f.write("2024-01-01 12:00:00 INFO User 42 logged in\n")
            f.write("2024-01-01 12:05:00 ERROR Database timeout\n")
            f.write("2024-01-01 12:05:05 ERROR Database timeout\n")
            f.write("2024-01-01 12:08:00 INFO API /users/profile took 250ms\n")
            f.write("2024-01-01 12:09:00 WARN Memory usage at 87%\n")
            f.write("2024-01-01 12:10:00 INFO User 42 logged out\n")
    
    run_pipeline()
