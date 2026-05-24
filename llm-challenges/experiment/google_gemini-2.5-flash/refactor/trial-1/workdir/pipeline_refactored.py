import datetime
import os
import re
import sqlite3
from typing import Dict, List, Any, Tuple

# Configuration loaded from environment variables
DB_PATH = os.getenv("DB_PATH", "metrics.db")
LOG_FILE = os.getenv("LOG_FILE", "server.log")
# DB_HOST, DB_PORT, DB_USER, DB_PASS are not directly used by sqlite3, but kept for consistency
# if this were to be adapted for a network database.
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_USER = os.getenv("DB_USER", "admin")
DB_PASS = os.getenv("DB_PASS", "password123")

# Regex patterns for log parsing
LOG_PATTERN = re.compile(r"^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) (?P<level>\w+) (?P<message>.*)$")
USER_LOGIN_PATTERN = re.compile(r"User (?P<user_id>\d+) logged in")
USER_LOGOUT_PATTERN = re.compile(r"User (?P<user_id>\d+) logged out")
API_CALL_PATTERN = re.compile(r"API (?P<endpoint>/\S+) took (?P<duration>\d+)ms")


def extract_logs(log_file_path: str) -> Tuple[List[Dict[str, Any]], Dict[str, str], List[Dict[str, Any]]]:
    """
    Extracts structured data from server logs using regex.

    Args:
        log_file_path: The path to the server log file.

    Returns:
        A tuple containing:
        - A list of dictionaries for all parsed log entries (errors, warnings, user actions, API calls).
        - A dictionary tracking active user sessions (user_id -> login_timestamp).
        - A list of dictionaries for API call metrics.
    """
    parsed_logs: List[Dict[str, Any]] = []
    active_sessions: Dict[str, str] = {}
    api_calls_raw: List[Dict[str, Any]] = []

    if not os.path.exists(log_file_path):
        print(f"Log file not found: {log_file_path}")
        return parsed_logs, active_sessions, api_calls_raw

    with open(log_file_path, "r") as f:
        for line in f:
            match = LOG_PATTERN.match(line)
            if not match:
                continue

            timestamp = match.group("timestamp")
            level = match.group("level")
            message = match.group("message")

            if level == "ERROR":
                parsed_logs.append({"timestamp": timestamp, "type": "ERR", "message": message.strip()})
            elif level == "WARN":
                parsed_logs.append({"timestamp": timestamp, "type": "WARN", "message": message.strip()})
            elif level == "INFO":
                user_login_match = USER_LOGIN_PATTERN.search(message)
                user_logout_match = USER_LOGOUT_PATTERN.search(message)
                api_call_match = API_CALL_PATTERN.search(message)

                if user_login_match:
                    user_id = user_login_match.group("user_id")
                    active_sessions[user_id] = timestamp
                    parsed_logs.append({"timestamp": timestamp, "type": "USR", "user_id": user_id, "action": message.strip()})
                elif user_logout_match:
                    user_id = user_logout_match.group("user_id")
                    if user_id in active_sessions:
                        active_sessions.pop(user_id)
                    parsed_logs.append({"timestamp": timestamp, "type": "USR", "user_id": user_id, "action": message.strip()})
                elif api_call_match:
                    endpoint = api_call_match.group("endpoint")
                    duration = int(api_call_match.group("duration"))
                    api_calls_raw.append({"timestamp": timestamp, "endpoint": endpoint, "duration_ms": duration})
                    parsed_logs.append({"timestamp": timestamp, "type": "API", "endpoint": endpoint, "duration_ms": duration})
    return parsed_logs, active_sessions, api_calls_raw


def transform_data(
    parsed_logs: List[Dict[str, Any]], api_calls_raw: List[Dict[str, Any]]
) -> Tuple[Dict[str, int], Dict[str, List[int]]]:
    """
    Transforms raw log data into summarized metrics.

    Args:
        parsed_logs: A list of all parsed log entries.
        api_calls_raw: A list of raw API call metrics.

    Returns:
        A tuple containing:
        - A dictionary with error messages as keys and their counts as values.
        - A dictionary with API endpoints as keys and a list of durations (ms) as values.
    """
    error_summary: Dict[str, int] = {}
    api_latency_raw: Dict[str, List[int]] = {}

    for log_entry in parsed_logs:
        if log_entry["type"] == "ERR":
            msg = log_entry["message"]
            error_summary[msg] = error_summary.get(msg, 0) + 1

    for call in api_calls_raw:
        endpoint = call["endpoint"]
        api_latency_raw.setdefault(endpoint, []).append(call["duration_ms"])
    
    return error_summary, api_latency_raw


def load_report(
    error_summary: Dict[str, int],
    api_latency_raw: Dict[str, List[int]],
    active_sessions_count: int,
    db_path: str,
    db_host: str,
    db_port: int,
    db_user: str,
) -> None:
    """
    Loads processed data into an SQLite database and generates an HTML report.

    Args:
        error_summary: Dictionary of error messages and their counts.
        api_latency_raw: Dictionary of API endpoints and lists of durations.
        active_sessions_count: The number of currently active user sessions.
        db_path: Path to the SQLite database file.
        db_host: Database host (for logging, not used by sqlite3).
        db_port: Database port (for logging, not used by sqlite3).
        db_user: Database user (for logging, not used by sqlite3).
    """
    print(f"Connecting to {db_host}:{db_port} as {db_user}...")
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    c.execute("CREATE TABLE IF NOT EXISTS errors (dt TEXT, message TEXT, count INTEGER)")
    c.execute("CREATE TABLE IF NOT EXISTS api_metrics (dt TEXT, endpoint TEXT, avg_ms REAL)")

    # Insert error summary data using parameterized queries
    for msg, count in error_summary.items():
        c.execute(
            "INSERT INTO errors (dt, message, count) VALUES (?, ?, ?)",
            (datetime.datetime.now().isoformat(), msg, count),
        )

    # Insert API metrics data using parameterized queries
    for ep, times in api_latency_raw.items():
        avg = sum(times) / len(times)
        c.execute(
            "INSERT INTO api_metrics (dt, endpoint, avg_ms) VALUES (?, ?, ?)",
            (datetime.datetime.now().isoformat(), ep, avg),
        )

    conn.commit()
    conn.close()

    # Generate HTML report
    out = "<html>\n<head><title>System Report</title></head>\n<body>\n"
    out += "<h1>Error Summary</h1>\n<ul>\n"
    for err_msg, count in error_summary.items():
        out += f"<li><b>{err_msg}</b>: {count} occurrences</li>\n"
    out += "</ul>\n"

    out += "<h2>API Latency</h2>\n<table border='1'>\n"
    out += "<tr><th>Endpoint</th><th>Avg (ms)</th></tr>\n"
    for ep, times in api_latency_raw.items():
        avg = sum(times) / len(times)
        out += f"<tr><td>{ep}</td><td>{round(avg, 1)}</td></tr>\n"
    out += "</table>\n"

    out += "<h2>Active Sessions</h2>\n"
    out += f"<p>{active_sessions_count} user(s) currently active</p>\n"
    out += "</body>\n</html>"

    with open("report.html", "w") as f:
        f.write(out)

    print(f"Job finished at {datetime.datetime.now()}")


def main() -> None:
    """
    Main function to orchestrate the log processing pipeline.
    """
    print("Starting log processing pipeline...")

    # Extract
    parsed_logs, active_sessions, api_calls_raw = extract_logs(LOG_FILE)
    print(f"Parsed Logs: {parsed_logs}")
    print(f"Active Sessions: {active_sessions}")
    print(f"API Calls Raw: {api_calls_raw}")

    # Transform
    error_summary, api_latency_raw = transform_data(parsed_logs, api_calls_raw)
    print(f"Error Summary: {error_summary}")
    print(f"API Latency Raw: {api_latency_raw}")

    # Load
    load_report(
        error_summary,
        api_latency_raw,
        len(active_sessions),
        DB_PATH,
        DB_HOST,
        DB_PORT,
        DB_USER,
    )


if __name__ == "__main__":
    # Create a dummy log file if it doesn't exist for demonstration
    if not os.path.exists(LOG_FILE):
        print(f"Creating dummy log file: {LOG_FILE}")
        with open(LOG_FILE, "w") as f:
            f.write("2024-01-01 12:00:00 INFO User 42 logged in\n")
            f.write("2024-01-01 12:05:00 ERROR Database timeout\n")
            f.write("2024-01-01 12:05:05 ERROR Database timeout\n")
            f.write("2024-01-01 12:08:00 INFO API /users/profile took 250ms\n")
            f.write("2024-01-01 12:09:00 WARN Memory usage at 87%\n")
            f.write("2024-01-01 12:10:00 INFO User 42 logged out\n")
            f.write("2024-01-01 12:15:00 INFO User 101 logged in\n")
            f.write("2024-01-01 12:20:00 INFO API /products/view took 120ms\n")

    main()
