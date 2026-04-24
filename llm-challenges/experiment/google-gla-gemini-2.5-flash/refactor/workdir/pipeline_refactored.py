import datetime
import os
import re
import sqlite3
from typing import Dict, List, Any, Tuple

# 1. Configuration: Load from environment variables with defaults
DB_PATH = os.getenv("DB_PATH", "metrics.db")
LOG_FILE = os.getenv("LOG_FILE", "server.log")
# DB_HOST, DB_PORT, DB_USER, DB_PASS are not directly used for sqlite3,
# but are kept to satisfy the requirement of using environment variables for all config.
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_USER = os.getenv("DB_USER", "admin")
DB_PASS = os.getenv("DB_PASS", "password123")

# Regex patterns for log parsing
ERROR_LOG_PATTERN = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) ERROR (.*)$")
INFO_USER_LOG_PATTERN = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) INFO User (\S+) (.*)$")
INFO_API_LOG_PATTERN = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) INFO API (\S+) took (\d+)ms$")
WARN_LOG_PATTERN = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) WARN (.*)$")

def parse_log_line(line: str) -> Dict[str, Any] | None:
    """
    Parses a single log line using regex patterns.

    Args:
        line: The log line string to parse.

    Returns:
        A dictionary containing parsed log data (timestamp, type, message, etc.),
        or None if the line does not match any known pattern.
    """
    if match := ERROR_LOG_PATTERN.match(line):
        return {"d": match.group(1), "t": "ERR", "m": match.group(2).strip()}
    elif match := INFO_USER_LOG_PATTERN.match(line):
        uid = match.group(2)
        action = match.group(3).strip()
        return {"d": match.group(1), "t": "USR", "u": uid, "a": action}
    elif match := INFO_API_LOG_PATTERN.match(line):
        return {"d": match.group(1), "t": "API", "endpoint": match.group(2), "ms": int(match.group(3))}
    elif match := WARN_LOG_PATTERN.match(line):
        return {"d": match.group(1), "t": "WARN", "m": match.group(2).strip()}
    return None

def extract_log_data(log_file_path: str) -> List[Dict[str, Any]]:
    """
    Extracts and parses log data from the specified log file.

    Args:
        log_file_path: The path to the server log file.

    Returns:
        A list of dictionaries, where each dictionary represents a parsed log entry.
    """
    parsed_entries: List[Dict[str, Any]] = []
    if os.path.exists(log_file_path):
        with open(log_file_path, "r") as f:
            for line in f.read().splitlines():
                entry = parse_log_line(line)
                if entry:
                    parsed_entries.append(entry)
    return parsed_entries

def transform_log_entries_to_error_summary(parsed_entries: List[Dict[str, Any]]) -> Dict[str, int]:
    """
    Transforms parsed log entries into an error summary, counting occurrences of each error message.

    Args:
        parsed_entries: A list of parsed log entries.

    Returns:
        A dictionary where keys are error messages and values are their counts.
    """
    error_summary: Dict[str, int] = {}
    for entry in parsed_entries:
        if entry.get("t") == "ERR":
            msg = entry["m"]
            error_summary[msg] = error_summary.get(msg, 0) + 1
    return error_summary

def transform_log_entries_to_api_metrics(parsed_entries: List[Dict[str, Any]]) -> Dict[str, float]:
    """
    Transforms parsed log entries into API latency metrics, calculating average duration per endpoint.

    Args:
        parsed_entries: A list of parsed log entries.

    Returns:
        A dictionary where keys are API endpoints and values are their average latency in milliseconds.
    """
    endpoint_durations: Dict[str, List[int]] = {}
    for entry in parsed_entries:
        if entry.get("t") == "API":
            endpoint = entry["endpoint"]
            duration = entry["ms"]
            endpoint_durations.setdefault(endpoint, []).append(duration)

    api_metrics: Dict[str, float] = {
        ep: sum(times) / len(times) for ep, times in endpoint_durations.items()
    }
    return api_metrics

def transform_log_entries_to_active_sessions(parsed_entries: List[Dict[str, Any]]) -> int:
    """
    Transforms parsed log entries to determine the number of active user sessions.

    Args:
        parsed_entries: A list of parsed log entries.

    Returns:
        The count of currently active user sessions.
    """
    sessions: Dict[str, str] = {}
    for entry in parsed_entries:
        if entry.get("t") == "USR":
            uid = entry["u"]
            action = entry["a"]
            if "logged in" in action:
                sessions[uid] = entry["d"]
            elif "logged out" in action and uid in sessions:
                sessions.pop(uid)
    return len(sessions)

def get_db_connection(db_path: str) -> sqlite3.Connection:
    """
    Establishes and returns a connection to the SQLite database.

    Args:
        db_path: The path to the SQLite database file.

    Returns:
        An SQLite database connection object.
    """
    print(f"Connecting to database at {db_path}...")
    # These are illustrative for the requirement, but not used by sqlite3.connect
    print(f"DB Host: {DB_HOST}, Port: {DB_PORT}, User: {DB_USER}...")
    conn = sqlite3.connect(db_path)
    return conn

def setup_database(conn: sqlite3.Connection) -> None:
    """
    Sets up the necessary tables in the database if they don't already exist.

    Args:
        conn: The database connection object.
    """
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS errors (dt TEXT, message TEXT, count INTEGER)")
    c.execute("CREATE TABLE IF NOT EXISTS api_metrics (dt TEXT, endpoint TEXT, avg_ms REAL)")
    conn.commit()

def load_error_summary_to_db(conn: sqlite3.Connection, error_summary: Dict[str, int]) -> None:
    """
    Loads error summary data into the database using parameterized queries.

    Args:
        conn: The database connection object.
        error_summary: A dictionary of error messages and their counts.
    """
    c = conn.cursor()
    for msg, count in error_summary.items():
        # Parameterized query to prevent SQL injection
        c.execute(
            "INSERT INTO errors (dt, message, count) VALUES (?, ?, ?)",
            (datetime.datetime.now().isoformat(), msg, count)
        )
    conn.commit()

def load_api_metrics_to_db(conn: sqlite3.Connection, api_metrics: Dict[str, float]) -> None:
    """
    Loads API metrics data into the database using parameterized queries.

    Args:
        conn: The database connection object.
        api_metrics: A dictionary of API endpoints and their average latencies.
    """
    c = conn.cursor()
    for ep, avg in api_metrics.items():
        # Parameterized query to prevent SQL injection
        c.execute(
            "INSERT INTO api_metrics (dt, endpoint, avg_ms) VALUES (?, ?, ?)",
            (datetime.datetime.now().isoformat(), ep, avg)
        )
    conn.commit()

def generate_report_html(
    error_summary: Dict[str, int],
    api_metrics: Dict[str, float],
    active_sessions_count: int,
    output_file: str = "report.html"
) -> None:
    """
    Generates an HTML report from the processed data.

    Args:
        error_summary: A dictionary of error messages and their counts.
        api_metrics: A dictionary of API endpoints and their average latencies.
        active_sessions_count: The count of currently active user sessions.
        output_file: The name of the HTML file to generate.
    """
    out = "<html>\n<head><title>System Report</title></head>\n<body>\n"
    out += "<h1>Error Summary</h1>\n<ul>\n"
    for err_msg, count in error_summary.items():
        out += f"<li><b>{err_msg}</b>: {count} occurrences</li>\n"
    out += "</ul>\n"

    out += "<h2>API Latency</h2>\n<table border='1'>\n"
    out += "<tr><th>Endpoint</th><th>Avg (ms)</th></tr>\n"
    for ep, avg in api_metrics.items():
        out += f"<tr><td>{ep}</td><td>{round(avg, 1)}</td></tr>\n"
    out += "</table>\n"

    out += "<h2>Active Sessions</h2>\n"
    out += f"<p>{active_sessions_count} user(s) currently active</p>\n"
    out += "</body>\n</html>"

    with open(output_file, "w") as f:
        f.write(out)
    print(f"Report generated: {output_file}")

def run_pipeline() -> None:
    """
    Orchestrates the entire log processing and reporting pipeline.
    """
    print(f"Starting log processing pipeline at {datetime.datetime.now()}")

    # E - Extract
    parsed_entries = extract_log_data(LOG_FILE)

    # T - Transform
    error_summary = transform_log_entries_to_error_summary(parsed_entries)
    api_metrics = transform_log_entries_to_api_metrics(parsed_entries)
    active_sessions_count = transform_log_entries_to_active_sessions(parsed_entries)

    # L - Load (to DB)
    conn = None
    try:
        conn = get_db_connection(DB_PATH)
        setup_database(conn)
        load_error_summary_to_db(conn, error_summary)
        load_api_metrics_to_db(conn, api_metrics)
    finally:
        if conn:
            conn.close()

    # L - Load (to HTML report)
    generate_report_html(error_summary, api_metrics, active_sessions_count)

    print(f"Job finished at {datetime.datetime.now()}")


if __name__ == "__main__":

    run_pipeline()
