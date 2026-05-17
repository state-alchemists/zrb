import datetime
import os
import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Generator, Iterable

# Configuration from environment variables
DB_PATH = Path(os.getenv("DB_PATH", "metrics.db"))
LOG_FILE_PATH = Path(os.getenv("LOG_FILE_PATH", "server.log"))
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_USER = os.getenv("DB_USER", "admin")
DB_PASS = os.getenv("DB_PASS", "password123")

@dataclass(frozen=True, slots=True)
class LogEntry:
    """Base class for log entries."""
    timestamp: str
    level: str

@dataclass(frozen=True, slots=True)
class ErrorEntry(LogEntry):
    """Represents an error log entry."""
    message: str

@dataclass(frozen=True, slots=True)
class UserEntry(LogEntry):
    """Represents a user action log entry."""
    user_id: str
    action: str

@dataclass(frozen=True, slots=True)
class ApiEntry(LogEntry):
    """Represents an API call log entry."""
    endpoint: str
    latency_ms: int

@dataclass(frozen=True, slots=True)
class WarnEntry(LogEntry):
    """Represents a warning log entry."""
    message: str

@dataclass(frozen=True, slots=True)
class ProcessedData:
    """Container for all aggregated data."""
    errors: dict[str, int] = field(default_factory=dict)
    api_latencies: dict[str, list[int]] = field(default_factory=dict)
    active_sessions: set[str] = field(default_factory=set)

def parse_log_line(line: str) -> LogEntry | None:
    """Parses a single log line into a LogEntry object."""
    match = re.match(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) (\w+) (.*)$", line)
    if not match:
        return None

    timestamp, level, content = match.groups()

    if level == "ERROR":
        return ErrorEntry(timestamp, level, content.strip())
    
    if level == "WARN":
        return WarnEntry(timestamp, level, content.strip())

    if level == "INFO":
        if user_match := re.match(r"User (\w+) (.*)", content):
            user_id, action = user_match.groups()
            return UserEntry(timestamp, level, user_id, action.strip())
        
        if api_match := re.match(r"API (\S+) took (\d+)ms", content):
            endpoint, duration = api_match.groups()
            return ApiEntry(timestamp, level, endpoint, int(duration))

    return None

def extract_logs(log_path: Path) -> Generator[LogEntry, None, None]:
    """Reads the log file and yields parsed log entries."""
    if not log_path.exists():
        return

    with log_path.open("r") as f:
        for line in f:
            if entry := parse_log_line(line):
                yield entry

def transform_data(entries: Iterable[LogEntry]) -> ProcessedData:
    """Aggregates log entries into reportable statistics."""
    data = ProcessedData()
    for entry in entries:
        match entry:
            case ErrorEntry(message=msg):
                data.errors[msg] = data.errors.get(msg, 0) + 1
            case ApiEntry(endpoint=ep, latency_ms=ms):
                data.api_latencies.setdefault(ep, []).append(ms)
            case UserEntry(user_id=uid, action=act):
                if "logged in" in act:
                    data.active_sessions.add(uid)
                elif "logged out" in act:
                    data.active_sessions.discard(uid)
    return data

def save_to_db(data: ProcessedData, db_path: Path) -> None:
    """Saves aggregated data to the database using parameterized queries."""
    now = datetime.datetime.now().isoformat()
    with sqlite3.connect(db_path) as conn:
        c = conn.cursor()
        c.execute("CREATE TABLE IF NOT EXISTS errors (dt TEXT, message TEXT, count INTEGER)")
        c.execute("CREATE TABLE IF NOT EXISTS api_metrics (dt TEXT, endpoint TEXT, avg_ms REAL)")

        for msg, count in data.errors.items():
            c.execute(
                "INSERT INTO errors (dt, message, count) VALUES (?, ?, ?)",
                (now, msg, count)
            )

        for ep, latencies in data.api_latencies.items():
            avg = sum(latencies) / len(latencies)
            c.execute(
                "INSERT INTO api_metrics (dt, endpoint, avg_ms) VALUES (?, ?, ?)",
                (now, ep, avg)
            )

def generate_html_report(data: ProcessedData, report_path: str = "report.html") -> None:
    """Generates an HTML report from processed data."""
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
    for ep, latencies in data.api_latencies.items():
        avg = round(sum(latencies) / len(latencies), 1)
        html_content.append(f"<tr><td>{ep}</td><td>{avg}</td></tr>")
    
    html_content.extend([
        "</table>",
        "<h2>Active Sessions</h2>",
        f"<p>{len(data.active_sessions)} user(s) currently active</p>",
        "</body>",
        "</html>"
    ])

    with open(report_path, "w") as f:
        f.write("\n".join(html_content))

def run_pipeline() -> None:
    """Main execution entry point for the pipeline."""
    print(f"Connecting to {DB_HOST}:{DB_PORT} as {DB_USER}...")
    
    entries = extract_logs(LOG_FILE_PATH)
    data = transform_data(entries)
    
    save_to_db(data, DB_PATH)
    generate_html_report(data)
    
    print(f"Job finished at {datetime.datetime.now()}")

if __name__ == "__main__":
    # Ensure log file exists for demo purposes if not present
    if not LOG_FILE_PATH.exists():
        with LOG_FILE_PATH.open("w") as f:
            f.write("2024-01-01 12:00:00 INFO User 42 logged in\n")
            f.write("2024-01-01 12:05:00 ERROR Database timeout\n")
            f.write("2024-01-01 12:05:05 ERROR Database timeout\n")
            f.write("2024-01-01 12:08:00 INFO API /users/profile took 250ms\n")
            f.write("2024-01-01 12:09:00 WARN Memory usage at 87%\n")
            f.write("2024-01-01 12:10:00 INFO User 42 logged out\n")
    
    run_pipeline()
