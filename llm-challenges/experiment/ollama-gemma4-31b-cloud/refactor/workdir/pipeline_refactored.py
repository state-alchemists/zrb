import datetime
import os
import re
import sqlite3
from dataclasses import dataclass
from typing import List, Dict, Any, Tuple, Optional

# Configuration from environment variables
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
    metadata: Dict[str, Any]

def extract_logs(file_path: str) -> List[LogEntry]:
    """
    Parses the server log file using regex to extract structured information.
    """
    entries = []
    # Regex pattern: timestamp (YYYY-MM-DD HH:MM:SS) level message
    log_pattern = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s+(\w+)\s+(.*)$")
    
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
                
            timestamp, level, message = match.groups()
            
            metadata = {}
            if level == "INFO":
                # User activity: "User <id> logged in/out"
                user_match = re.search(r"User (\S+) (logged in|logged out)", message)
                if user_match:
                    uid, action = user_match.groups()
                    metadata = {"type": "USER", "user_id": uid, "action": action}
                else:
                    # API call: "API <endpoint> took <ms>ms"
                    api_match = re.search(r"API (\S+) took (\d+)ms", message)
                    if api_match:
                        endpoint, duration = api_match.groups()
                        metadata = {"type": "API", "endpoint": endpoint, "duration": int(duration)}
            
            entries.append(LogEntry(timestamp, level, message, metadata))
            
    return entries

def transform_metrics(entries: List[LogEntry]) -> Tuple[Dict[str, int], Dict[str, List[int]], int]:
    """
    Processes log entries to calculate error summaries, API latencies, and active sessions.
    """
    error_counts: Dict[str, int] = {}
    api_latencies: Dict[str, List[int]] = {}
    active_users = set()

    for entry in entries:
        # Error aggregation
        if entry.level == "ERROR":
            error_counts[entry.message] = error_counts.get(entry.message, 0) + 1
        
        # User session tracking
        if entry.metadata.get("type") == "USER":
            uid = entry.metadata["user_id"]
            action = entry.metadata["action"]
            if action == "logged in":
                active_users.add(uid)
            elif action == "logged out":
                active_users.discard(uid)
        
        # API latency tracking
        if entry.metadata.get("type") == "API":
            ep = entry.metadata["endpoint"]
            duration = entry.metadata["duration"]
            api_latencies.setdefault(ep, []).append(duration)

    return error_counts, api_latencies, len(active_users)

def load_to_db(error_counts: Dict[str, int], api_latencies: Dict[str, List[int]]) -> None:
    """
    Persists metrics to the SQLite database using parameterized queries.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("CREATE TABLE IF NOT EXISTS errors (dt TEXT, message TEXT, count INTEGER)")
    cursor.execute("CREATE TABLE IF NOT EXISTS api_metrics (dt TEXT, endpoint TEXT, avg_ms REAL)")

    now = datetime.datetime.now().isoformat()

    # Load Errors
    error_data = [(now, msg, count) for msg, count in error_counts.items()]
    cursor.executemany("INSERT INTO errors VALUES (?, ?, ?)", error_data)

    # Load API Metrics
    api_data = []
    for ep, times in api_latencies.items():
        avg = sum(times) / len(times)
        api_data.append((now, ep, avg))
    cursor.executemany("INSERT INTO api_metrics VALUES (?, ?, ?)", api_data)

    conn.commit()
    conn.close()

def generate_report(error_counts: Dict[str, int], api_latencies: Dict[str, List[int]], session_count: int) -> None:
    """
    Generates the HTML report with system metrics.
    """
    html = [
        "<html>",
        "<head><title>System Report</title></head>",
        "<body>",
        "<h1>Error Summary</h1>",
        "<ul>"
    ]
    
    for msg, count in error_counts.items():
        html.append(f"<li><b>{msg}</b>: {count} occurrences</li>")
    
    html.append("</ul>")
    html.append("<h2>API Latency</h2>")
    html.append("<table border='1'>")
    html.append("<tr><th>Endpoint</th><th>Avg (ms)</th></tr>")
    
    for ep, times in api_latencies.items():
        avg = sum(times) / len(times)
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
    Main orchestration logic for the log processing pipeline.
    """
    print(f"Connecting to {DB_HOST}:{DB_PORT} as {DB_USER}...")
    
    # Extract
    entries = extract_logs(LOG_FILE)
    
    # Transform
    error_counts, api_latencies, session_count = transform_metrics(entries)
    
    # Load
    load_to_db(error_counts, api_latencies)
    generate_report(error_counts, api_latencies, session_count)
    
    print(f"Job finished at {datetime.datetime.now()}")

if __name__ == "__main__":
    # Setup dummy data if log file missing (preserving original behavior)
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, "w") as f:
            f.write("2024-01-01 12:00:00 INFO User 42 logged in\n")
            f.write("2024-01-01 12:05:00 ERROR Database timeout\n")
            f.write("2024-01-01 12:05:05 ERROR Database timeout\n")
            f.write("2024-01-01 12:08:00 INFO API /users/profile took 250ms\n")
            f.write("2024-01-01 12:09:00 WARN Memory usage at 87%\n")
            f.write("2024-01-01 12:10:00 INFO User 42 logged out\n")
            
    run_pipeline()
