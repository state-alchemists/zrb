import datetime
import os
import re
import sqlite3
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Tuple

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
    metadata: Dict[str, Any]

# Regex patterns for log parsing
LOG_PATTERN = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s+(\w+)\s+(.*)$")
USER_PATTERN = re.compile(r"User (\S+) (logged in|logged out)")
API_PATTERN = re.compile(r"API (\S+) took (\d+)ms")

def extract_logs(file_path: str) -> List[LogEntry]:
    """Parses the log file into a list of LogEntry objects."""
    entries = []
    if not os.path.exists(file_path):
        return entries

    with open(file_path, "r") as f:
        for line in f:
            line = line.strip()
            match = LOG_PATTERN.match(line)
            if not match:
                continue

            timestamp, level, content = match.groups()
            metadata = {}

            if level == "INFO":
                # Check for User activity
                user_match = USER_PATTERN.search(content)
                if user_match:
                    uid, action = user_match.groups()
                    metadata = {"type": "USR", "user_id": uid, "action": action}
                
                # Check for API activity
                api_match = API_PATTERN.search(content)
                if api_match:
                    endpoint, latency = api_match.groups()
                    metadata = {"type": "API", "endpoint": endpoint, "latency": int(latency)}

            elif level == "ERROR":
                metadata = {"type": "ERR"}
            elif level == "WARN":
                metadata = {"type": "WARN"}

            entries.append(LogEntry(timestamp, level, content, metadata))
    
    return entries

def transform_data(entries: List[LogEntry]) -> Tuple[Dict[str, int], Dict[str, List[int]], int]:
    """Processes raw log entries into aggregated metrics."""
    error_counts: Dict[str, int] = {}
    api_latencies: Dict[str, List[int]] = {}
    active_sessions = set()

    for entry in entries:
        meta = entry.metadata
        
        if meta.get("type") == "ERR":
            msg = entry.message
            error_counts[msg] = error_counts.get(msg, 0) + 1
        
        elif meta.get("type") == "API":
            ep = meta["endpoint"]
            api_latencies.setdefault(ep, []).append(meta["latency"])
            
        elif meta.get("type") == "USR":
            uid = meta["user_id"]
            action = meta["action"]
            if action == "logged in":
                active_sessions.add(uid)
            elif action == "logged out":
                active_sessions.discard(uid)

    return error_counts, api_latencies, len(active_sessions)

def load_to_db(error_counts: Dict[str, int], api_latencies: Dict[str, List[int]]) -> None:
    """Saves aggregated metrics to the SQLite database using parameterized queries."""
    print(f"Connecting to {DB_HOST}:{DB_PORT} as {DB_USER}...")
    
    with sqlite3.connect(DB_PATH) as conn:
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
            avg = sum(times) / len(times) if times else 0
            api_data.append((now, ep, avg))
        cursor.executemany("INSERT INTO api_metrics VALUES (?, ?, ?)", api_data)

        conn.commit()

def generate_report(error_counts: Dict[str, int], api_latencies: Dict[str, List[int]], sessions_count: int) -> None:
    """Generates the HTML report with the same format as the original pipeline."""
    html = ["<html>", "<head><title>System Report</title></head>", "<body>"]
    
    # Error Summary
    html.append("<h1>Error Summary</h1>")
    html.append("<ul>")
    for msg, count in error_counts.items():
        html.append(f"<li><b>{msg}</b>: {count} occurrences</li>")
    html.append("</ul>")

    # API Latency
    html.append("<h2>API Latency</h2>")
    html.append("<table border='1'>")
    html.append("<tr><th>Endpoint</th><th>Avg (ms)</th></tr>")
    for ep, times in api_latencies.items():
        avg = sum(times) / len(times) if times else 0
        html.append(f"<tr><td>{ep}</td><td>{round(avg, 1)}</td></tr>")
    html.append("</table>")

    # Active Sessions
    html.append("<h2>Active Sessions</h2>")
    html.append(f"<p>{sessions_count} user(s) currently active</p>")
    
    html.append("</body>")
    html.append("</html>")

    with open("report.html", "w") as f:
        f.write("\n".join(html))

def run_pipeline() -> None:
    """Main orchestration function for the ETL pipeline."""
    # 1. Extract
    entries = extract_logs(LOG_FILE)
    
    # 2. Transform
    error_counts, api_latencies, sessions_count = transform_data(entries)
    
    # 3. Load
    load_to_db(error_counts, api_latencies)
    generate_report(error_counts, api_latencies, sessions_count)
    
    print(f"Job finished at {datetime.datetime.now()}")

if __name__ == "__main__":
    # Create dummy log file if it doesn't exist for testing
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, "w") as f:
            f.write("2024-01-01 12:00:00 INFO User 42 logged in\n")
            f.write("2024-01-01 12:05:00 ERROR Database timeout\n")
            f.write("2024-01-01 12:05:05 ERROR Database timeout\n")
            f.write("2024-01-01 12:08:00 INFO API /users/profile took 250ms\n")
            f.write("2024-01-01 12:09:00 WARN Memory usage at 87%\n")
            f.write("2024-01-01 12:10:00 INFO User 42 logged out\n")
    
    run_pipeline()
