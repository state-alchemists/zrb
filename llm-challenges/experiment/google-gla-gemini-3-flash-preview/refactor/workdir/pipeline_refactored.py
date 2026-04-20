import datetime
import os
import re
import sqlite3
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

# Configuration from environment variables
DB_PATH = os.getenv("DB_PATH", "metrics.db")
LOG_FILE = os.getenv("LOG_FILE", "server.log")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_USER = os.getenv("DB_USER", "admin")
DB_PASS = os.getenv("DB_PASS", "password123")


@dataclass
class LogEntry:
    dt: str
    level: str
    message: str


@dataclass
class PipelineData:
    errors: Dict[str, int] = field(default_factory=dict)
    api_metrics: Dict[str, List[int]] = field(default_factory=dict)
    active_sessions: Set[str] = field(default_factory=set)


def extract_logs(log_file_path: str) -> List[LogEntry]:
    """
    Reads the log file and parses lines into LogEntry objects.
    """
    entries = []
    if not os.path.exists(log_file_path):
        return entries

    log_pattern = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) (\w+) (.*)$")

    with open(log_file_path, "r") as f:
        for line in f:
            match = log_pattern.match(line.strip())
            if match:
                dt, level, message = match.groups()
                entries.append(LogEntry(dt, level, message))
    return entries


def transform_logs(entries: List[LogEntry]) -> PipelineData:
    """
    Transforms raw log entries into structured pipeline data.
    """
    data = PipelineData()
    user_pattern = re.compile(r"User (\w+) (.*)")
    api_pattern = re.compile(r"API (\S+)(?: took (\d+)ms)?")

    for entry in entries:
        if entry.level == "ERROR":
            data.errors[entry.message] = data.errors.get(entry.message, 0) + 1
        
        elif entry.level == "INFO":
            # Check for User actions
            user_match = user_pattern.search(entry.message)
            if user_match:
                uid, action = user_match.groups()
                if "logged in" in action:
                    data.active_sessions.add(uid)
                elif "logged out" in action:
                    data.active_sessions.discard(uid)
            
            # Check for API calls
            api_match = api_pattern.search(entry.message)
            if api_match:
                endpoint, duration = api_match.groups()
                latency = int(duration) if duration else 0
                if endpoint not in data.api_metrics:
                    data.api_metrics[endpoint] = []
                data.api_metrics[endpoint].append(latency)
                
    return data

def load_to_db(data: PipelineData, db_path: str) -> None:
    """
    Loads transformed data into the SQLite database using parameterized queries.
    """
    print(f"Connecting to {DB_HOST}:{DB_PORT} as {DB_USER}...")
    
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        
        # Create tables
        cursor.execute("CREATE TABLE IF NOT EXISTS errors (dt TEXT, message TEXT, count INTEGER)")
        cursor.execute("CREATE TABLE IF NOT EXISTS api_metrics (dt TEXT, endpoint TEXT, avg_ms REAL)")
        
        now = datetime.datetime.now().isoformat()
        
        # Insert errors
        error_records = [(now, msg, count) for msg, count in data.errors.items()]
        cursor.executemany("INSERT INTO errors VALUES (?, ?, ?)", error_records)
        
        # Insert API metrics
        api_records = []
        for endpoint, times in data.api_metrics.items():
            avg_latency = sum(times) / len(times) if times else 0.0
            api_records.append((now, endpoint, avg_latency))
        
        cursor.executemany("INSERT INTO api_metrics VALUES (?, ?, ?)", api_records)
        
        conn.commit()

def generate_report(data: PipelineData, output_path: str) -> None:
    """
    Generates an HTML report from the pipeline data.
    """
    html_content = [
        "<html>",
        "<head><title>System Report</title></head>",
        "<body>",
        "<h1>Error Summary</h1>",
        "<ul>"
    ]
    
    for msg, count in data.errors.items():
        html_content.append(f"<li><b>{msg}</b>: {count} occurrences</li>")
    
    html_content.extend([
        "</ul>",
        "<h2>API Latency</h2>",
        "<table border='1'>",
        "<tr><th>Endpoint</th><th>Avg (ms)</th></tr>"
    ])
    
    for endpoint, times in data.api_metrics.items():
        avg_latency = round(sum(times) / len(times), 1) if times else 0.0
        html_content.append(f"<tr><td>{endpoint}</td><td>{avg_latency}</td></tr>")
        
    html_content.extend([
        "</table>",
        "<h2>Active Sessions</h2>",
        f"<p>{len(data.active_sessions)} user(s) currently active</p>",
        "</body>",
        "</html>"
    ])
    
    with open(output_path, "w") as f:
        f.write("\n".join(html_content))


def main() -> None:
    """
    Main execution flow.
    """
    # Ensure log file exists for demonstration if it doesn't
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, "w") as f:
            f.write("2024-01-01 12:00:00 INFO User 42 logged in\n")
            f.write("2024-01-01 12:05:00 ERROR Database timeout\n")
            f.write("2024-01-01 12:05:05 ERROR Database timeout\n")
            f.write("2024-01-01 12:08:00 INFO API /users/profile took 250ms\n")
            f.write("2024-01-01 12:09:00 WARN Memory usage at 87%\n")
            f.write("2024-01-01 12:10:00 INFO User 42 logged out\n")

    # Extract
    entries = extract_logs(LOG_FILE)
    
    # Transform
    data = transform_logs(entries)
    
    # Load
    load_to_db(data, DB_PATH)
    
    # Report
    generate_report(data, "report.html")
    
    print(f"Job finished at {datetime.datetime.now()}")


if __name__ == "__main__":
    main()
