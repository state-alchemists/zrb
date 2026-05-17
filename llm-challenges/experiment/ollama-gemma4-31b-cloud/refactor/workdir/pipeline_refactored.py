import os
import re
import sqlite3
import datetime
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass

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
    content: str
    category: str  # ERR, USR, API, WARN

def parse_logs(file_path: str) -> Tuple[List[LogEntry], Dict[str, str], List[Dict[str, Any]]]:
    """
    Extracts information from server logs using regex.
    
    Returns:
        A tuple containing:
        - A list of general log entries (Errors, Warnings, User events).
        - A dictionary of active sessions {user_id: login_time}.
        - A list of API call metrics.
    """
    entries: List[LogEntry] = []
    sessions: Dict[str, str] = {}
    api_calls: List[Dict[str, Any]] = []

    # Regex patterns for different log levels and types
    # Log format: YYYY-MM-DD HH:MM:SS LEVEL Message
    log_pattern = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) (\w+) (.+)$")
    user_pattern = re.compile(r"User (\S+) (.+)$")
    api_pattern = re.compile(r"API (\S+)(?: took (\d+)ms)?")

    if not os.path.exists(file_path):
        return entries, sessions, api_calls

    with open(file_path, "r") as f:
        for line in f:
            line = line.strip()
            match = log_pattern.match(line)
            if not match:
                continue
            
            timestamp, level, content = match.groups()

            if level == "ERROR":
                entries.append(LogEntry(timestamp, level, content, "ERR"))
            
            elif level == "WARN":
                entries.append(LogEntry(timestamp, level, content, "WARN"))
            
            elif level == "INFO":
                # Check for User activity
                user_match = user_pattern.search(content)
                if user_match:
                    uid, action = user_match.groups()
                    if "logged in" in action:
                        sessions[uid] = timestamp
                    elif "logged out" in action:
                        sessions.pop(uid, None)
                    entries.append(LogEntry(timestamp, level, content, "USR"))
                    continue
                
                # Check for API activity
                api_match = api_pattern.search(content)
                if api_match:
                    endpoint, duration = api_match.groups()
                    api_calls.append({
                        "timestamp": timestamp,
                        "endpoint": endpoint,
                        "ms": int(duration) if duration else 0
                    })

    return entries, sessions, api_calls

def transform_data(entries: List[LogEntry], api_calls: List[Dict[str, Any]]) -> Tuple[Dict[str, int], Dict[str, List[int]]]:
    """
    Aggregates raw log entries into summary statistics.
    """
    error_counts: Dict[str, int] = {}
    for entry in entries:
        if entry.category == "ERR":
            error_counts[entry.content] = error_counts.get(entry.content, 0) + 1

    api_stats: Dict[str, List[int]] = {}
    for call in api_calls:
        ep = call["endpoint"]
        api_stats.setdefault(ep, []).append(call["ms"])

    return error_counts, api_stats

def load_to_db(error_summary: Dict[str, int], api_stats: Dict[str, List[int]]) -> None:
    """
    Loads aggregated metrics into the SQLite database using parameterized queries.
    """
    print(f"Connecting to {DB_HOST}:{DB_PORT} as {DB_USER}...")
    
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE IF NOT EXISTS errors (dt TEXT, message TEXT, count INTEGER)")
        cursor.execute("CREATE TABLE IF NOT EXISTS api_metrics (dt TEXT, endpoint TEXT, avg_ms REAL)")
        
        now = datetime.datetime.now().isoformat()

        # Use parameterized queries to prevent SQL injection
        for msg, count in error_summary.items():
            cursor.execute("INSERT INTO errors VALUES (?, ?, ?)", (now, msg, count))

        for ep, times in api_stats.items():
            avg = sum(times) / len(times) if times else 0
            cursor.execute("INSERT INTO api_metrics VALUES (?, ?, ?)", (now, ep, avg))
        
        conn.commit()

def generate_report(error_summary: Dict[str, int], api_stats: Dict[str, List[int]], active_sessions_count: int, output_path: str = "report.html") -> None:
    """
    Generates an HTML report with the summarized system metrics.
    """
    html = [
        "<html>",
        "<head><title>System Report</title></head>",
        "<body>",
        "<h1>Error Summary</h1>",
        "<ul>"
    ]
    
    for msg, count in error_summary.items():
        html.append(f"<li><b>{msg}</b>: {count} occurrences</li>")
    
    html.append("</ul>")
    html.append("<h2>API Latency</h2>")
    html.append("<table border='1'>")
    html.append("<tr><th>Endpoint</th><th>Avg (ms)</th></tr>")
    
    for ep, times in api_stats.items():
        avg = sum(times) / len(times) if times else 0
        html.append(f"<tr><td>{ep}</td><td>{round(avg, 1)}</td></tr>")
    
    html.append("</table>")
    html.append("<h2>Active Sessions</h2>")
    html.append(f"<p>{active_sessions_count} user(s) currently active</p>")
    html.append("</body>")
    html.append("</html>")

    with open(output_path, "w") as f:
        f.write("\n".join(html))

def run_pipeline() -> None:
    """
    Orchestrates the Extract, Transform, Load, and Report process.
    """
    # Extract
    entries, sessions, api_calls = parse_logs(LOG_FILE)
    
    # Transform
    error_summary, api_stats = transform_data(entries, api_calls)
    
    # Load
    load_to_db(error_summary, api_stats)
    
    # Report
    generate_report(error_summary, api_stats, len(sessions))
    
    print(f"Job finished at {datetime.datetime.now()}")

if __name__ == "__main__":
    # Mock data creation for testing purposes (matching original script behavior)
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, "w") as f:
            f.write("2024-01-01 12:00:00 INFO User 42 logged in\n")
            f.write("2024-01-01 12:05:00 ERROR Database timeout\n")
            f.write("2024-01-01 12:05:05 ERROR Database timeout\n")
            f.write("2024-01-01 12:08:00 INFO API /users/profile took 250ms\n")
            f.write("2024-01-01 12:09:00 WARN Memory usage at 87%\n")
            f.write("2024-01-01 12:10:00 INFO User 42 logged out\n")
    
    run_pipeline()
