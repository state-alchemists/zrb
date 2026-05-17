import datetime
import os
import re
import sqlite3
from dataclasses import dataclass
from typing import Any, Dict

def transform_logs(log_entries: list[Dict[str, Any]]) -> tuple[Dict[str, int], Dict[str, list[int]], Dict[str, str]]:
    """
    Transforms raw log entries into structured data for reporting.

    Args:
        log_entries: A list of dictionaries, each representing a parsed log entry.

    Returns:
        A tuple containing:
            - error_summary: A dictionary mapping error messages to their counts.
            - api_latency_stats: A dictionary mapping API endpoints to a list of latencies (in ms).
            - active_sessions: A dictionary mapping user IDs to their login timestamps.
    """
    error_summary: Dict[str, int] = {}
    api_latency_stats: Dict[str, list[int]] = {}
    active_sessions: Dict[str, str] = {}

    for entry in log_entries:
        if entry["type"] == "error":
            message = entry["message"]
            error_summary[message] = error_summary.get(message, 0) + 1
        elif entry["type"] == "user_event":
            user_id = entry["user_id"]
            action = entry["action"]
            if "logged in" in action:
                active_sessions[user_id] = entry["timestamp"]
            elif "logged out" in action and user_id in active_sessions:
                active_sessions.pop(user_id)
        elif entry["type"] == "api_call":
            endpoint = entry["endpoint"]
            duration = entry["duration_ms"]
            api_latency_stats.setdefault(endpoint, []).append(duration)
    return error_summary, api_latency_stats, active_sessions
import os
import re
import sqlite3
from dataclasses import dataclass
from typing import Any, Dict

@dataclass
class Config:
    """Configuration for the log processing pipeline."""
    db_path: str
    log_file_path: str
    db_host: str
    db_port: int
    db_user: str
    db_pass: str

def load_config() -> Config:
    """Loads configuration from environment variables."""
    return Config(
        db_path=os.getenv("DB_PATH", "metrics.db"),
        log_file_path=os.getenv("LOG_FILE_PATH", "server.log"),
        db_host=os.getenv("DB_HOST", "localhost"),
        db_port=int(os.getenv("DB_PORT", "5432")),
        db_user=os.getenv("DB_USER", "admin"),
        db_pass=os.getenv("DB_PASS", "password123"),
    )


def extract_logs(log_file_path: str) -> list[Dict[str, Any]]:
    """
    Extracts structured log data from a log file.

    Args:
        log_file_path: The path to the server log file.

    Returns:
        A list of dictionaries, each representing a parsed log entry.
    """
    log_entries = []
    # Regex to parse log lines:
    # (timestamp) (INFO|ERROR|WARN) (message)
    log_pattern = re.compile(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) (INFO|ERROR|WARN) (.*)")
    user_action_pattern = re.compile(r"User (\d+) (.*)")
    api_call_pattern = re.compile(r"API (\S+) took (\d+)ms")

    if os.path.exists(log_file_path):
        with open(log_file_path, "r") as f:
            for line in f:
                match = log_pattern.match(line)
                if match:
                    timestamp_str, level, message = match.groups()
                    entry: Dict[str, Any] = {"timestamp": timestamp_str, "level": level, "message": message.strip()}

                    if level == "INFO":
                        user_match = user_action_pattern.search(message)
                        api_match = api_call_pattern.search(message)

                        if user_match:
                            user_id, action = user_match.groups()
                            entry["type"] = "user_event"
                            entry["user_id"] = user_id
                            entry["action"] = action.strip()
                        elif api_match:
                            endpoint, duration = api_match.groups()
                            entry["type"] = "api_call"
                            entry["endpoint"] = endpoint
                            entry["duration_ms"] = int(duration)
                        else:
                            entry["type"] = "info_message"
                    elif level == "ERROR":
                        entry["type"] = "error"
                    elif level == "WARN":
                        entry["type"] = "warning"
                    log_entries.append(entry)
    return log_entries

def connect_db(db_path: str) -> sqlite3.Connection:
    """
    Establishes a connection to the SQLite database.

    Args:
        db_path: The path to the SQLite database file.

    Returns:
        A SQLite connection object.
    """
    print(f"Connecting to database: {db_path}...")
    return sqlite3.connect(db_path)

def create_tables(conn: sqlite3.Connection) -> None:
    """
    Creates necessary tables in the database if they don't exist.

    Args:
        conn: The SQLite connection object.
    """
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS errors (dt TEXT, message TEXT, count INTEGER)")
    c.execute("CREATE TABLE IF NOT EXISTS api_metrics (dt TEXT, endpoint TEXT, avg_ms REAL)")
    conn.commit()

def insert_error_summary(conn: sqlite3.Connection, error_summary: Dict[str, int]) -> None:
    """
    Inserts error summary data into the database.

    Args:
        conn: The SQLite connection object.
        error_summary: A dictionary mapping error messages to their counts.
    """
    c = conn.cursor()
    current_time = datetime.datetime.now().isoformat()
    for msg, count in error_summary.items():
        c.execute("INSERT INTO errors (dt, message, count) VALUES (?, ?, ?)",
                  (current_time, msg, count))
    conn.commit()

def insert_api_metrics(conn: sqlite3.Connection, api_latency_stats: Dict[str, list[int]]) -> None:
    """
    Inserts API latency metrics into the database.

    Args:
        conn: The SQLite connection object.
        api_latency_stats: A dictionary mapping API endpoints to a list of latencies (in ms).
    """
    c = conn.cursor()
    current_time = datetime.datetime.now().isoformat()
    for ep, times in api_latency_stats.items():
        avg = sum(times) / len(times)
        c.execute("INSERT INTO api_metrics (dt, endpoint, avg_ms) VALUES (?, ?, ?)",
                  (current_time, ep, avg))
    conn.commit()


def generate_report_html(error_summary: Dict[str, int], api_latency_stats: Dict[str, list[int]], active_sessions: Dict[str, str]) -> str:
    """
    Generates an HTML report summarizing system metrics.

    Args:
        error_summary: A dictionary mapping error messages to their counts.
        api_latency_stats: A dictionary mapping API endpoints to a list of latencies (in ms).
        active_sessions: A dictionary mapping user IDs to their login timestamps.

    Returns:
        A string containing the complete HTML report.
    """
    out = "<html>\n<head><title>System Report</title></head>\n<body>\n"
    out += "<h1>Error Summary</h1>\n<ul>\n"
    for err_msg, count in error_summary.items():
        out += f"<li><b>{err_msg}</b>: {count} occurrences</li>\n"
    out += "</ul>\n"

    out += "<h2>API Latency</h2>\n<table border='1'>\n"
    out += "<tr><th>Endpoint</th><th>Avg (ms)</th></tr>\n"
    for ep, times in api_latency_stats.items():
        avg = sum(times) / len(times)
        out += f"<tr><td>{ep}</td><td>{round(avg, 1)}</td></tr>\n"
    out += "</table>\n"

    out += "<h2>Active Sessions</h2>\n"
    out += f"<p>{len(active_sessions)} user(s) currently active</p>\n"
    out += "</body>\n</html>"
    return out



def main() -> None:
    """
    Main function to run the log processing pipeline.
    """
    config = load_config()

    # Extract
    log_entries = extract_logs(config.log_file_path)

    # Transform
    error_summary, api_latency_stats, active_sessions = transform_logs(log_entries)

    # Load to DB
    conn = connect_db(config.db_path)
    try:
        create_tables(conn)
        insert_error_summary(conn, error_summary)
        insert_api_metrics(conn, api_latency_stats)
    finally:
        conn.close()

    # Load to HTML report
    html_report_content = generate_report_html(error_summary, api_latency_stats, active_sessions)
    with open("report.html", "w") as f:
        f.write(html_report_content)

    print(f"Report generated at {datetime.datetime.now()}")


if __name__ == "__main__":
    config = load_config()
    if not os.path.exists(config.log_file_path):
        with open(config.log_file_path, "w") as f:
            f.write("2024-01-01 12:00:00 INFO User 42 logged in\n")
            f.write("2024-01-01 12:05:00 ERROR Database timeout\n")
            f.write("2024-01-01 12:05:05 ERROR Database timeout\n")
            f.write("2024-01-01 12:08:00 INFO API /users/profile took 250ms\n")
            f.write("2024-01-01 12:09:00 WARN Memory usage at 87%\n")
            f.write("2024-01-01 12:10:00 INFO User 42 logged out\n")
    main()
