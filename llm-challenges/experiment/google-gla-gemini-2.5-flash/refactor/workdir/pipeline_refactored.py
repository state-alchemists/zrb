import datetime
import os
import re
import sqlite3
from typing import Dict, List, Any, Optional, Tuple

# Configuration from environment variables
DB_PATH = os.getenv("DB_PATH", "metrics.db")
LOG_FILE = os.getenv("LOG_FILE", "server.log")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_USER = os.getenv("DB_USER", "admin")
DB_PASS = os.getenv("DB_PASS", "password123")

def parse_log_line(line: str) -> Optional[Dict[str, Any]]:
    """
    Parses a single log line using regex to extract structured information.

    Args:
        line: The log line string to parse.

    Returns:
        A dictionary containing parsed log data (timestamp, level, message, etc.)
        or None if the line does not match expected patterns.
    """
    # Example log patterns:
    # 2024-01-01 12:00:00 INFO User 42 logged in
    # 2024-01-01 12:05:00 ERROR Database timeout
    # 2024-01-01 12:08:00 INFO API /users/profile took 250ms
    # 2024-01-01 12:09:00 WARN Memory usage at 87%

    log_pattern = re.compile(
        r"^(?P<date>\d{4}-\d{2}-\d{2})\s(?P<time>\d{2}:\d{2}:\d{2})\s"
        r"(?P<level>[A-Z]+)\s(?P<message>.*)$"
    )
    match = log_pattern.match(line)

    if not match:
        return None

    data = match.groupdict()
    timestamp = f"{data['date']} {data['time']}"
    level = data['level']
    message = data['message']

    if level == "ERROR":
        return {"d": timestamp, "t": "ERR", "m": message.strip()}
    elif level == "INFO":
        if "User" in message:
            user_match = re.search(r"User\s(?P<uid>\d+)\s(?P<action>.*)", message)
            if user_match:
                user_data = user_match.groupdict()
                return {"d": timestamp, "t": "USR", "u": user_data['uid'], "a": user_data['action'].strip()}
        elif "API" in message:
            api_match = re.search(r"API\s(?P<endpoint>/\S+)(?:\stook\s(?P<ms>\d+)ms)?", message)
            if api_match:
                api_data = api_match.groupdict()
                duration = int(api_data['ms']) if api_data['ms'] else 0
                return {"d": timestamp, "t": "API", "endpoint": api_data['endpoint'], "ms": duration}
    elif level == "WARN":
        return {"d": timestamp, "t": "WARN", "m": message.strip()}

    return None

def extract_log_data(log_file_path: str) -> List[Dict[str, Any]]:
    """
    Reads a log file, parses each line, and returns a list of structured log entries.

    Args:
        log_file_path: The path to the server log file.

    Returns:
        A list of dictionaries, each representing a parsed log entry.
    """
    log_entries: List[Dict[str, Any]] = []
    if os.path.exists(log_file_path):
        with open(log_file_path, "r") as f:
            for line in f:
                parsed_line = parse_log_line(line)
                if parsed_line:
                    log_entries.append(parsed_line)
    return log_entries


def process_log_entries(log_entries: List[Dict[str, Any]]) -> Tuple[Dict[str, int], Dict[str, List[int]], Dict[str, str]]:
    """
    Processes a list of parsed log entries to aggregate error counts, API latencies,
    and track active user sessions.

    Args:
        log_entries: A list of dictionaries, each representing a parsed log entry.

    Returns:
        A tuple containing three dictionaries:
        - error_summary: Keys are error messages, values are their counts.
        - api_latency_data: Keys are API endpoints, values are lists of latencies (ms).
        - active_sessions: Keys are user IDs, values are their login timestamps.
    """
    error_summary: Dict[str, int] = {}
    api_latency_data: Dict[str, List[int]] = {}
    active_sessions: Dict[str, str] = {}

    for entry in log_entries:
        if entry["t"] == "ERR":
            msg = entry["m"]
            error_summary[msg] = error_summary.get(msg, 0) + 1
        elif entry["t"] == "USR":
            uid = entry["u"]
            action = entry["a"]
            if "logged in" in action:
                active_sessions[uid] = entry["d"]
            elif "logged out" in action and uid in active_sessions:
                active_sessions.pop(uid)
        elif entry["t"] == "API":
            endpoint = entry["endpoint"]
            api_latency_data.setdefault(endpoint, []).append(entry["ms"])

    return error_summary, api_latency_data, active_sessions



def setup_database(db_path: str) -> sqlite3.Connection:
    """
    Establishes a connection to the SQLite database and creates necessary tables if they don't exist.

    Args:
        db_path: The path to the SQLite database file.

    Returns:
        A sqlite3.Connection object.
    """
    print(f"Connecting to database: {DB_HOST}:{DB_PORT} as {DB_USER}...")
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS errors (dt TEXT, message TEXT, count INTEGER)")
    c.execute("CREATE TABLE IF NOT EXISTS api_metrics (dt TEXT, endpoint TEXT, avg_ms REAL)")
    conn.commit()
    return conn

def insert_error_summary(conn: sqlite3.Connection, error_summary: Dict[str, int]) -> None:
    """
    Inserts error summary data into the 'errors' table using parameterized queries.

    Args:
        conn: The SQLite database connection object.
        error_summary: A dictionary with error messages as keys and their counts as values.
    """
    c = conn.cursor()
    now = datetime.datetime.now()
    for msg, count in error_summary.items():
        c.execute("INSERT INTO errors VALUES (?, ?, ?)", (now, msg, count))
    conn.commit()

def insert_api_metrics(conn: sqlite3.Connection, api_latency_data: Dict[str, List[int]]) -> None:
    """
    Calculates average API latencies and inserts them into the 'api_metrics' table
    using parameterized queries.

    Args:
        conn: The SQLite database connection object.
        api_latency_data: A dictionary with API endpoints as keys and lists of latencies as values.
    """
    c = conn.cursor()
    now = datetime.datetime.now()
    for ep, times in api_latency_data.items():
        if times:
            avg = sum(times) / len(times)
            c.execute("INSERT INTO api_metrics VALUES (?, ?, ?)", (now, ep, avg))
    conn.commit()


def generate_report(
    error_summary: Dict[str, int],
    api_latency_data: Dict[str, List[int]],
    active_sessions: Dict[str, str],
) -> str:
    """
    Generates an HTML report string based on processed log data.

    Args:
        error_summary: A dictionary with error messages and their counts.
        api_latency_data: A dictionary with API endpoints and lists of their latencies.
        active_sessions: A dictionary with active user IDs and their login timestamps.

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
    for ep, times in api_latency_data.items():
        if times:
            avg = sum(times) / len(times)
            out += f"<tr><td>{ep}</td><td>{round(avg, 1)}</td></tr>\n"
    out += "</table>\n"

    out += "<h2>Active Sessions</h2>\n"
    out += f"<p>{len(active_sessions)} user(s) currently active</p>\n"
    out += "</body>\n</html>"
    return out

def write_report_file(report_content: str, output_path: str) -> None:
    """
    Writes the generated HTML report content to a specified file.

    Args:
        report_content: The HTML string content of the report.
        output_path: The path where the report file should be saved.
    """
    with open(output_path, "w") as f:
        f.write(report_content)
    print(f"Report generated at {output_path} at {datetime.datetime.now()}")


def main():
    """
    Main function to orchestrate the log processing, data transformation,
    database loading, and report generation.
    """
    log_entries = extract_log_data(LOG_FILE)
    error_summary, api_latency_data, active_sessions = process_log_entries(log_entries)

    conn = None
    try:
        conn = setup_database(DB_PATH)
        insert_error_summary(conn, error_summary)
        insert_api_metrics(conn, api_latency_data)
    finally:
        if conn:
            conn.close()

    report_content = generate_report(error_summary, api_latency_data, active_sessions)
    write_report_file(report_content, "report.html")


if __name__ == "__main__":
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, "w") as f:
            f.write("2024-01-01 12:00:00 INFO User 42 logged in\n")
            f.write("2024-01-01 12:05:00 ERROR Database timeout\n")
            f.write("2024-01-01 12:05:05 ERROR Database timeout\n")
            f.write("2024-01-01 12:08:00 INFO API /users/profile took 250ms\n")
            f.write("2024-01-01 12:09:00 WARN Memory usage at 87%\n")
            f.write("2024-01-01 12:10:00 INFO User 42 logged out\n")
    main()
