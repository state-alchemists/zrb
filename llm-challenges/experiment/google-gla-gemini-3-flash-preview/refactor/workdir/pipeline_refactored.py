import datetime
import os
import re
import sqlite3
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass

# Configuration from Environment Variables
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

@dataclass
class ProcessedData:
    errors: Dict[str, int]
    api_metrics: Dict[str, List[int]]
    active_sessions: int

def extract_logs(file_path: str) -> List[LogEntry]:
    """
    Reads the log file and extracts log entries using regex.
    """
    entries = []
    if not os.path.exists(file_path):
        return entries

    # Pattern: 2024-01-01 12:00:00 INFO Message
    log_pattern = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) (\w+) (.*)$")

    with open(file_path, "r") as f:
        for line in f:
            match = log_pattern.match(line.strip())
            if match:
                entries.append(LogEntry(
                    timestamp=match.group(1),
                    level=match.group(2),
                    message=match.group(3)
                ))
    return entries

def transform_data(entries: List[LogEntry]) -> ProcessedData:
    """
    Processes log entries into structured metrics.
    """
    errors = {}
    sessions = set()
    api_calls = {}

    # Regex for sub-parsing
    user_pattern = re.compile(r"User (\w+) (.*)")
    api_pattern = re.compile(r"API (\S+) took (\d+)ms")

    for entry in entries:
        if entry.level == "ERROR":
            errors[entry.message] = errors.get(entry.message, 0) + 1
        
        elif entry.level == "INFO":
            # Check for User sessions
            user_match = user_pattern.search(entry.message)
            if user_match:
                uid, action = user_match.groups()
                if "logged in" in action:
                    sessions.add(uid)
                elif "logged out" in action:
                    sessions.discard(uid)
            
            # Check for API metrics
            api_match = api_pattern.search(entry.message)
            if api_match:
                endpoint, duration = api_match.groups()
                api_calls.setdefault(endpoint, []).append(int(duration))

    return ProcessedData(
        errors=errors,
        api_metrics=api_calls,
        active_sessions=len(sessions)
    )

def load_to_database(data: ProcessedData, db_path: str) -> None:
    """
    Saves processed metrics to the database using parameterized queries.
    """
    print(f"Connecting to {DB_HOST}:{DB_PORT} as {DB_USER}...")
    
    conn = sqlite3.connect(db_path)
    try:
        c = conn.cursor()
        c.execute("CREATE TABLE IF NOT EXISTS errors (dt TEXT, message TEXT, count INTEGER)")
        c.execute("CREATE TABLE IF NOT EXISTS api_metrics (dt TEXT, endpoint TEXT, avg_ms REAL)")

        now = datetime.datetime.now().isoformat()

        # Insert errors
        error_entries = [(now, msg, count) for msg, count in data.errors.items()]
        c.executemany("INSERT INTO errors VALUES (?, ?, ?)", error_entries)

        # Insert API metrics
        api_entries = []
        for ep, times in data.api_metrics.items():
            avg = sum(times) / len(times)
            api_entries.append((now, ep, avg))
        c.executemany("INSERT INTO api_metrics VALUES (?, ?, ?)", api_entries)

        conn.commit()
    finally:
        conn.close()

def generate_report(data: ProcessedData, output_file: str) -> None:
    """
    Generates an HTML report from the processed data.
    """
    html_lines = [
        "<html>",
        "<head><title>System Report</title></head>",
        "<body>",
        "<h1>Error Summary</h1>",
        "<ul>"
    ]

    for err_msg, count in data.errors.items():
        html_lines.append(f"<li><b>{err_msg}</b>: {count} occurrences</li>")
    
    html_lines.extend([
        "</ul>",
        "<h2>API Latency</h2>",
        "<table border='1'>",
        "<tr><th>Endpoint</th><th>Avg (ms)</th></tr>"
    ])

    for ep, times in data.api_metrics.items():
        avg = sum(times) / len(times)
        html_lines.append(f"<tr><td>{ep}</td><td>{round(avg, 1)}</td></tr>")
    
    html_lines.extend([
        "</table>",
        "<h2>Active Sessions</h2>",
        f"<p>{data.active_sessions} user(s) currently active</p>",
        "</body>",
        "</html>"
    ])

    with open(output_file, "w") as f:
        f.write("\n".join(html_lines))

def run_pipeline():
    """
    Executes the full ETL pipeline.
    """
    # ETL Process
    entries = extract_logs(LOG_FILE)
    processed_data = transform_data(entries)
    load_to_database(processed_data, DB_PATH)
    generate_report(processed_data, "report.html")

    print(f"Job finished at {datetime.datetime.now()}")

if __name__ == "__main__":
    # Setup dummy log if not exists for demonstration
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, "w") as f:
            f.write("2024-01-01 12:00:00 INFO User 42 logged in\n")
            f.write("2024-01-01 12:05:00 ERROR Database timeout\n")
            f.write("2024-01-01 12:05:05 ERROR Database timeout\n")
            f.write("2024-01-01 12:08:00 INFO API /users/profile took 250ms\n")
            f.write("2024-01-01 12:09:00 WARN Memory usage at 87%\n")
            f.write("2024-01-01 12:10:00 INFO User 42 logged out\n")
    
    run_pipeline()
