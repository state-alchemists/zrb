import datetime
import os
import re
import sqlite3
from dataclasses import dataclass
from typing import Dict, List, Any

@dataclass
class LogEntry:
    timestamp: str
    level: str
    message: str
    user_id: str | None = None
    action: str | None = None
    endpoint: str | None = None
    duration_ms: int | None = None

class Config:
    """Configuration class for the pipeline, loading values from environment variables."""
    DB_PATH: str = os.getenv("DB_PATH", "metrics.db")
    LOG_FILE: str = os.getenv("LOG_FILE", "server.log")
    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_PORT: int = int(os.getenv("DB_PORT", "5432"))
    DB_USER: str = os.getenv("DB_USER", "admin")
    DB_PASS: str = os.getenv("DB_PASS", "password123")

LOG_LINE_REGEX = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) "
    r"(?P<level>[A-Z]+) "
    r"(?P<message>.*)$"
)
USER_LOGIN_REGEX = re.compile(r"User (?P<user_id>\d+) logged in")
USER_LOGOUT_REGEX = re.compile(r"User (?P<user_id>\d+) logged out")
API_CALL_REGEX = re.compile(r"API (?P<endpoint>/\S+) took (?P<duration>\d+)ms")


def _parse_log_line(line: str) -> LogEntry | None:
    """
    Parses a single log line using regex and returns a LogEntry object.
    """
    match = LOG_LINE_REGEX.match(line)
    if not match:
        return None

    data = match.groupdict()
    timestamp = data["timestamp"]
    level = data["level"]
    message = data["message"].strip()

    if level == "INFO":
        user_login_match = USER_LOGIN_REGEX.search(message)
        if user_login_match:
            user_id = user_login_match.group("user_id")
            return LogEntry(timestamp, level, message, user_id=user_id, action="logged in")

        user_logout_match = USER_LOGOUT_REGEX.search(message)
        if user_logout_match:
            user_id = user_logout_match.group("user_id")
            return LogEntry(timestamp, level, message, user_id=user_id, action="logged out")

        api_call_match = API_CALL_REGEX.search(message)
        if api_call_match:
            endpoint = api_call_match.group("endpoint")
            duration_ms = int(api_call_match.group("duration"))
            return LogEntry(timestamp, level, message, endpoint=endpoint, duration_ms=duration_ms)

    return LogEntry(timestamp, level, message)


def read_logs(log_file_path: str) -> List[LogEntry]:
    """
    Reads log entries from the specified log file, parses each line, and returns a list of LogEntry objects.
    """
    parsed_logs: List[LogEntry] = []
    if os.path.exists(log_file_path):
        with open(log_file_path, "r") as f:
            for line in f:
                log_entry = _parse_log_line(line)
                if log_entry:
                    parsed_logs.append(log_entry)
    return parsed_logs


def _summarize_errors(parsed_logs: List[LogEntry]) -> Dict[str, int]:
    """
    Summarizes error messages and their counts from the parsed log entries.
    """
    error_summary: Dict[str, int] = {}
    for entry in parsed_logs:
        if entry.level == "ERROR":
            error_summary[entry.message] = error_summary.get(entry.message, 0) + 1
    return error_summary


def _calculate_api_latency(parsed_logs: List[LogEntry]) -> Dict[str, float]:
    """
    Calculates the average API latency for each endpoint from the parsed log entries.
    """
    endpoint_durations: Dict[str, List[int]] = {}
    for entry in parsed_logs:
        if entry.level == "INFO" and entry.endpoint and entry.duration_ms is not None:
            endpoint_durations.setdefault(entry.endpoint, []).append(entry.duration_ms)

    api_latency: Dict[str, float] = {
        ep: sum(times) / len(times) for ep, times in endpoint_durations.items()
    }
    return api_latency


def _track_sessions(parsed_logs: List[LogEntry]) -> int:
    """
    Tracks active user sessions based on login/logout events and returns the count of currently active sessions.
    """
    active_sessions: Dict[str, str] = {}
    for entry in parsed_logs:
        if entry.level == "INFO" and entry.user_id:
            if entry.action == "logged in":
                active_sessions[entry.user_id] = entry.timestamp
            elif entry.action == "logged out" and entry.user_id in active_sessions:
                active_sessions.pop(entry.user_id)
    return len(active_sessions)


class DatabaseManager:
    """Manages database connections and operations."""
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn: sqlite3.Connection | None = None

    def __enter__(self):
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.conn:
            self.conn.commit()
            self.conn.close()

    def create_tables(self) -> None:
        """Creates the necessary tables if they don't exist."""
        if self.cursor:
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS errors (
                    dt TEXT,
                    message TEXT,
                    count INTEGER
                )
            """)
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS api_metrics (
                    dt TEXT,
                    endpoint TEXT,
                    avg_ms REAL
                )
            """)

    def insert_errors(self, error_summary: Dict[str, int]) -> None:
        """Inserts error summaries into the database using parameterized queries."""
        if self.cursor:
            current_time = datetime.datetime.now().isoformat()
            for msg, count in error_summary.items():
                self.cursor.execute(
                    "INSERT INTO errors (dt, message, count) VALUES (?, ?, ?)",
                    (current_time, msg, count),
                )

    def insert_api_metrics(self, api_latency: Dict[str, float]) -> None:
        """Inserts API latency metrics into the database using parameterized queries."""
        if self.cursor:
            current_time = datetime.datetime.now().isoformat()
            for ep, avg in api_latency.items():
                self.cursor.execute(
                    "INSERT INTO api_metrics (dt, endpoint, avg_ms) VALUES (?, ?, ?)",
                    (current_time, ep, avg),
                )


def generate_report_html(
    error_summary: Dict[str, int], api_latency: Dict[str, float], active_sessions_count: int
) -> str:
    """
    Generates the HTML report content based on the processed data.
    """
    out = """<html>
<head><title>System Report</title></head>
<body>
<h1>Error Summary</h1>
<ul>
"""
    for err_msg, count in error_summary.items():
        out += f"<li><b>{err_msg}</b>: {count} occurrences</li>\n"
    out += "</ul>\n"

    out += "<h2>API Latency</h2>\n<table border='1'>\n"
    out += "<tr><th>Endpoint</th><th>Avg (ms)</th></tr>\n"
    for ep, avg in api_latency.items():
        out += f"<tr><td>{ep}</td><td>{round(avg, 1)}</td></tr>\n"
    out += "</table>\n"

    out += "<h2>Active Sessions</h2>\n"
    out += f"<p>{active_sessions_count} user(s) currently active</p>\n"
    out += "</body>\n</html>"
    return out


def write_report_file(report_content: str, output_file_path: str) -> None:
    """
    Writes the generated HTML report content to a file.
    """
    with open(output_file_path, "w") as f:
        f.write(report_content)


def main():
    """
    Main function to run the log processing and reporting pipeline.
    """
    config = Config()

    print(f"Connecting to {config.DB_HOST}:{config.DB_PORT} as {config.DB_USER}...")

    # Extract
    parsed_logs = read_logs(config.LOG_FILE)

    # Transform
    error_summary = _summarize_errors(parsed_logs)
    api_latency = _calculate_api_latency(parsed_logs)
    active_sessions_count = _track_sessions(parsed_logs)

    # Load
    with DatabaseManager(config.DB_PATH) as db_manager:
        db_manager.create_tables()
        db_manager.insert_errors(error_summary)
        db_manager.insert_api_metrics(api_latency)

    report_content = generate_report_html(error_summary, api_latency, active_sessions_count)
    write_report_file("report.html", report_content)

    print(f"Job finished at {datetime.datetime.now()}")


if __name__ == "__main__":
    if not os.path.exists(Config.LOG_FILE):
        with open(Config.LOG_FILE, "w") as f:
            f.write("2024-01-01 12:00:00 INFO User 42 logged in\n")
            f.write("2024-01-01 12:05:00 ERROR Database timeout\n")
            f.write("2024-01-01 12:05:05 ERROR Database timeout\n")
            f.write("2024-01-01 12:08:00 INFO API /users/profile took 250ms\n")
            f.write("2024-01-01 12:09:00 WARN Memory usage at 87%\n")
            f.write("2024-01-01 12:10:00 INFO User 42 logged out\n")
    main()

