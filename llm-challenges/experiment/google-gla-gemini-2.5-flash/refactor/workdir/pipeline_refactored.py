import datetime
import os
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple


@dataclass(frozen=True, slots=True)
class Config:
    """Configuration for the log processing pipeline."""
    db_path: Path
    log_file_path: Path
    db_host: str
    db_port: int
    db_user: str
    db_pass: str


@dataclass
class LogEntry:
    """Represents a parsed log entry."""
    timestamp: datetime.datetime
    level: str
    message: Optional[str] = None
    user_id: Optional[str] = None
    action: Optional[str] = None
    endpoint: Optional[str] = None
    duration_ms: Optional[int] = None


def load_config() -> Config:
    """Loads configuration from environment variables."""
    db_path = Path(os.getenv("DB_PATH", "metrics.db"))
    log_file_path = Path(os.getenv("LOG_FILE", "server.log"))
    db_host = os.getenv("DB_HOST", "localhost")
    db_port = int(os.getenv("DB_PORT", "5432"))
    db_user = os.getenv("DB_USER", "admin")
    db_pass = os.getenv("DB_PASS", "password123")
    return Config(db_path, log_file_path, db_host, db_port, db_user, db_pass)


def main():
    print(f"Connecting to {config.db_host}:{config.db_port} as {config.db_user}...")

def parse_log_line(line: str) -> Optional[LogEntry]:
    """Parses a single log line using regex and returns a LogEntry object."""
    # Regex to match common log patterns
    # Example: 2024-01-01 12:00:00 INFO User 42 logged in
    # Example: 2024-01-01 12:05:00 ERROR Database timeout
    # Example: 2024-01-01 12:08:00 INFO API /users/profile took 250ms

def parse_log_line(line: str) -> Optional[LogEntry]:
    """Parses a single log line using regex and returns a LogEntry object."""
    # Regex for ERROR and WARN messages
    error_warn_pattern = re.compile(
        r"^(?P<date>\d{4}-\d{2}-\d{2}) (?P<time>\d{2}:\d{2}:\d{2}) "
        r"(?P<level>ERROR|WARN) (?P<message>.*)$"
    )
    # Regex for INFO User messages
    info_user_pattern = re.compile(
        r"^(?P<date>\d{4}-\d{2}-\d{2}) (?P<time>\d{2}:\d{2}:\d{2}) "
        r"INFO User (?P<user_id>\d+) (?P<user_action>.*)$"
    )
    # Regex for INFO API messages
    info_api_pattern = re.compile(
        r"^(?P<date>\d{4}-\d{2}-\d{2}) (?P<time>\d{2}:\d{2}:\d{2}) "
        r"INFO API (?P<endpoint>/\S+) took (?P<duration>\d+)ms$"
    )
    # Regex for generic INFO messages
    generic_info_pattern = re.compile(
        r"^(?P<date>\d{4}-\d{2}-\d{2}) (?P<time>\d{2}:\d{2}:\d{2}) "
        r"INFO (?P<message>.*)$"
    )

    line = line.strip()
    timestamp: datetime.datetime

    match = error_warn_pattern.match(line)
    if match:
        return LogEntry(timestamp=timestamp, level=data['level'], message=data['message'].strip())

    match = info_user_pattern.match(line)
    if match:
        data = match.groupdict()
        timestamp = datetime.datetime.strptime(f"{data['date']} {data['time']}", "%Y-%m-%d %H:%M:%S")
        return LogEntry(
            timestamp=timestamp, level="INFO", user_id=data['user_id'], action=data['user_action'].strip()
        )

    match = info_api_pattern.match(line)
    if match:
        data = match.groupdict()
        timestamp = datetime.datetime.strptime(f"{data['date']} {data['time']}", "%Y-%m-%d %H:%M:%S")
        return LogEntry(
            timestamp=timestamp, level="INFO", endpoint=data['endpoint'], duration_ms=int(data['duration'])
        )
    
    match = generic_info_pattern.match(line)
    if match:
        data = match.groupdict()
        timestamp = datetime.datetime.strptime(f"{data['date']} {data['time']}", "%Y-%m-%d %H:%M:%S")
        return LogEntry(timestamp=timestamp, level="INFO", message=data['message'].strip())

    return None

def extract_log_data(log_file_path: Path) -> List[LogEntry]:
    """
    Extracts log entries from the specified log file.

    Args:
        log_file_path: The path to the log file.

    Returns:
        A list of parsed LogEntry objects.
    """
    log_entries: List[LogEntry] = []
    if log_file_path.exists():
        with open(log_file_path, "r") as f:
            for line in f:
                entry = parse_log_line(line)
                if entry:
                    log_entries.append(entry)
    return log_entries

def process_log_entries(
    log_entries: List[LogEntry]
) -> Tuple[Dict[str, int], Dict[str, List[int]], Dict[str, datetime.datetime]]:
    """
    Processes a list of log entries to generate error summaries, API latency statistics,
    and active user sessions.

    Args:
        log_entries: A list of LogEntry objects.

    Returns:
        A tuple containing:
        - error_summary: A dictionary mapping error messages to their counts.
        - api_latency_stats: A dictionary mapping API endpoints to a list of their latencies in ms.
        - active_sessions: A dictionary mapping user IDs to their login timestamps (datetime objects).
    """
    error_summary: Dict[str, int] = {}
    api_latency_stats: Dict[str, List[int]] = {}
    active_sessions: Dict[str, datetime.datetime] = {}

    for entry in log_entries:
        if entry.level == "ERROR" and entry.message:
            error_summary[entry.message] = error_summary.get(entry.message, 0) + 1
        elif entry.level == "INFO":
            if entry.user_id and entry.action:
                if "logged in" in entry.action:
                    active_sessions[entry.user_id] = entry.timestamp
                elif "logged out" in entry.action and entry.user_id in active_sessions:
                    active_sessions.pop(entry.user_id)
            elif entry.endpoint and entry.duration_ms is not None:
                api_latency_stats.setdefault(entry.endpoint, []).append(entry.duration_ms)
    
    return error_summary, api_latency_stats, active_sessions

def initialize_database(db_path: Path) -> sqlite3.Connection:
    """
    Initializes the SQLite database and creates necessary tables.

    Args:
        db_path: The path to the SQLite database file.

    Returns:
        A connection object to the database.
    """
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS errors (dt TEXT, message TEXT, count INTEGER)")
    c.execute("CREATE TABLE IF NOT EXISTS api_metrics (dt TEXT, endpoint TEXT, avg_ms REAL)")
    conn.commit()
    return conn

def insert_error_summary(conn: sqlite3.Connection, error_summary: Dict[str, int]):
    """
    Inserts error summary data into the database using parameterized queries.

    Args:
        conn: The database connection object.
        error_summary: A dictionary mapping error messages to their counts.
    """
    c = conn.cursor()
    for msg, count in error_summary.items():
        c.execute(
            "INSERT INTO errors (dt, message, count) VALUES (?, ?, ?)",
            (datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), msg, count),
        )
    conn.commit()

def insert_api_metrics(conn: sqlite3.Connection, api_latency_stats: Dict[str, List[int]]):
    """
    Inserts API latency metrics into the database using parameterized queries.

    Args:
        conn: The database connection object.
        api_latency_stats: A dictionary mapping API endpoints to a list of their latencies.
    """
    c = conn.cursor()
    for ep, times in api_latency_stats.items():
        avg = sum(times) / len(times)
        c.execute(
            "INSERT INTO api_metrics (dt, endpoint, avg_ms) VALUES (?, ?, ?)",
            (datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), ep, avg),
        )
    conn.commit()

def generate_report(
    error_summary: Dict[str, int],
    api_latency_stats: Dict[str, List[int]],
    active_sessions: Dict[str, datetime.datetime],
) -> str:
    """
    Generates an HTML report from the processed log data.

    Args:
        error_summary: A dictionary mapping error messages to their counts.
        api_latency_stats: A dictionary mapping API endpoints to a list of their latencies.
        active_sessions: A dictionary mapping user IDs to their login timestamps.

    Returns:
        A string containing the HTML report.
    """
    out = "<html>\n<head><title>System Report</title></head>\n<body>\n"
    out += "<h1>Error Summary</h1>\n<ul>\n"
    for err_msg, count in error_summary.items():
        out += f"<li><b>{err_msg}</b>: {count} occurrences</li>\n"
    out += "</ul>\n"

    out += "<h2>API Latency</h2>\n<table border=\'1\'>\n"
    out += "<tr><th>Endpoint</th><th>Avg (ms)</th></tr>\n"
    for ep, times in api_latency_stats.items():
        avg = sum(times) / len(times)
        out += f"<tr><td>{ep}</td><td>{round(avg, 1)}</td></tr>\n"
    out += "</table>\n"

    out += "<h2>Active Sessions</h2>\n"
    out += f"<p>{len(active_sessions)} user(s) currently active</p>\n"
    out += "</body>\n</html>"
    return out

def write_report_file(report_content: str, output_path: Path):
    """
    Writes the generated HTML report to a file.

    Args:
        report_content: The HTML content of the report.
        output_path: The path to the output HTML file.
    """
    with open(output_path, "w") as f:
        f.write(report_content)

def main():
    config = load_config()
    print(f"Connecting to {config.db_host}:{config.db_port} as {config.db_user}...")

    log_entries = extract_log_data(config.log_file_path)
    error_summary, api_latency_stats, active_sessions = process_log_entries(log_entries)

    conn = initialize_database(config.db_path)
    insert_error_summary(conn, error_summary)
    insert_api_metrics(conn, api_latency_stats)
    conn.close()

    report_content = generate_report(error_summary, api_latency_stats, active_sessions)
    write_report_file(report_content, Path("report.html"))

    print("Job finished at " + str(datetime.datetime.now()))


if __name__ == "__main__":
    config = load_config()
    if not config.log_file_path.exists():
        with open(config.log_file_path, "w") as f:
            f.write("2024-01-01 12:00:00 INFO User 42 logged in\n")
            f.write("2024-01-01 12:05:00 ERROR Database timeout\n")
            f.write("2024-01-01 12:05:05 ERROR Database timeout\n")
            f.write("2024-01-01 12:08:00 INFO API /users/profile took 250ms\n")
            f.write("2024-01-01 12:09:00 WARN Memory usage at 87%\n")
            f.write("2024-01-01 12:10:00 INFO User 42 logged out\n")
    main()
