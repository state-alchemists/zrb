import datetime
import os
import re
import sqlite3
from typing import Dict, List, Any, Tuple

# --- Configuration (from Environment Variables) ---
DB_PATH = os.getenv("DB_PATH", "metrics.db")
LOG_FILE = os.getenv("LOG_FILE", "server.log")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_USER = os.getenv("DB_USER", "admin")
DB_PASS = os.getenv("DB_PASS", "password123")

# --- Regex patterns for log parsing ---
LOG_LINE_PATTERN = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) "
    r"(?P<level>(INFO|ERROR|WARN)) "
    r"(?P<message>.*)$"
)
USER_INFO_PATTERN = re.compile(r"User (?P<user_id>\d+) (?P<action>.*)")
API_INFO_PATTERN = re.compile(r"API (?P<endpoint>/\S+) took (?P<duration>\d+)ms")


def extract_log_data(log_file_path: str) -> List[str]:
    """
    Extracts raw log lines from the specified log file.

    Args:
        log_file_path (str): The path to the server log file.

    Returns:
        List[str]: A list of raw log lines.
    """
    if not os.path.exists(log_file_path):
        print(f"Log file not found: {log_file_path}")
        return []

    with open(log_file_path, "r") as f:
        return f.readlines()


def parse_log_entries(
    log_lines: List[str],
) -> Tuple[List[Dict[str, Any]], Dict[str, str], List[Dict[str, Any]]]:
    """
    Parses raw log lines into structured data, identifying errors, user sessions,
    and API calls.

    Args:
        log_lines (List[str]): A list of raw log lines.

    Returns:
        Tuple[List[Dict[str, Any]], Dict[str, str], List[Dict[str, Any]]]:
            - d_list (List[Dict[str, Any]]): Processed log entries (ERR, USR, WARN).
            - sessions (Dict[str, str]): Currently active user sessions (user_id -> login_time).
            - api_calls (List[Dict[str, Any]]): Details of API calls (timestamp, endpoint, duration).
    """
    d_list: List[Dict[str, Any]] = []
    sessions: Dict[str, str] = {}
    api_calls: List[Dict[str, Any]] = []

    for line in log_lines:
        print(f"Processing line: {line.strip()}")
        match = LOG_LINE_PATTERN.match(line)
        if not match:
            print(f"No main log pattern match for line: {line.strip()}")
            continue

        timestamp = match.group("timestamp")
        level = match.group("level")
        message = match.group("message")
        print(f"Extracted: Timestamp={timestamp}, Level={level}, Message={message.strip()}")

        if level == "ERROR":
            d_list.append({"d": timestamp, "t": "ERR", "m": message.strip()})
        elif level == "INFO":
            if "User" in message:
                user_match = USER_INFO_PATTERN.match(message)
                if user_match:
                    user_id = user_match.group("user_id")
                    action = user_match.group("action").strip()
                    if "logged in" in action:
                        sessions[user_id] = timestamp
                    elif "logged out" in action and user_id in sessions:
                        sessions.pop(user_id)
                    d_list.append({"d": timestamp, "t": "USR", "u": user_id, "a": action})
            elif "API" in message:
                api_match = API_INFO_PATTERN.match(message)
                if api_match:
                    endpoint = api_match.group("endpoint")
                    duration = int(api_match.group("duration"))
                    api_calls.append({"d": timestamp, "endpoint": endpoint, "ms": duration})
        elif level == "WARN":
            d_list.append({"d": timestamp, "t": "WARN", "m": message.strip()})
    return d_list, sessions, api_calls


def load_data_to_db(
    db_path: str,
    error_summary: Dict[str, int],
    api_latency_data: Dict[str, List[int]],
) -> None:
    """
    Connects to the SQLite database and loads processed error and API latency data.
    Uses parameterized queries to prevent SQL injection.

    Args:
        db_path (str): Path to the SQLite database file.
        error_summary (Dict[str, int]): A dictionary where keys are error messages
                                         and values are their counts.
        api_latency_data (Dict[str, List[int]]): A dictionary where keys are API endpoints
                                                 and values are lists of latency times in ms.
    """
    print(
        f"Connecting to database at {db_path} (Host: {DB_HOST}:{DB_PORT}, User: {DB_USER})..."
    )
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    c.execute("CREATE TABLE IF NOT EXISTS errors (dt TEXT, message TEXT, count INTEGER)")
    c.execute("CREATE TABLE IF NOT EXISTS api_metrics (dt TEXT, endpoint TEXT, avg_ms REAL)")

    # Insert error summaries
    for msg, count in error_summary.items():
        c.execute(
            "INSERT INTO errors (dt, message, count) VALUES (?, ?, ?)",
            (datetime.datetime.now().isoformat(), msg, count),
        )

    # Insert API metrics
    for ep, times in api_latency_data.items():
        if times:
            avg = sum(times) / len(times)
            c.execute(
                "INSERT INTO api_metrics (dt, endpoint, avg_ms) VALUES (?, ?, ?)",
                (datetime.datetime.now().isoformat(), ep, avg),
            )

    conn.commit()
    conn.close()


def generate_report_html(
    error_summary: Dict[str, int],
    api_latency_data: Dict[str, List[int]],
    active_sessions_count: int,
    output_file: str = "report.html",
) -> None:
    """
    Generates an HTML report summarizing log analysis data.

    Args:
        error_summary (Dict[str, int]): A dictionary where keys are error messages
                                         and values are their counts.
        api_latency_data (Dict[str, List[int]]): A dictionary where keys are API endpoints
                                                 and values are lists of latency times in ms.
        active_sessions_count (int): The number of currently active user sessions.
        output_file (str): The name of the HTML file to generate.
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
    out += f"<p>{active_sessions_count} user(s) currently active</p>\n"
    out += "</body>\n</html>"

    with open(output_file, "w") as f:
        f.write(out)


def main() -> None:
    """
    Main function to orchestrate the log processing and reporting pipeline.
    """
    log_lines = extract_log_data(LOG_FILE)
    d_list, sessions, api_calls = parse_log_entries(log_lines)

    # Transform: Aggregate data for database and report
    error_summary: Dict[str, int] = {}
    for entry in d_list:
        if entry["t"] == "ERR":
            msg = entry["m"]
            error_summary[msg] = error_summary.get(msg, 0) + 1

    api_latency_data: Dict[str, List[int]] = {}
    for call in api_calls:
        api_latency_data.setdefault(call["endpoint"], []).append(call["ms"])

    load_data_to_db(DB_PATH, error_summary, api_latency_data)
    print(f"Error Summary before report: {error_summary}")
    print(f"API Latency Data before report: {api_latency_data}")
    generate_report_html(error_summary, api_latency_data, len(sessions))

    print(f"Job finished at {datetime.datetime.now()}")


if __name__ == "__main__":
    # Create a dummy log file if it doesn't exist for demonstration
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, "w") as f:
            f.write("2024-01-01 12:00:00 INFO User 42 logged in\n")
            f.write("2024-01-01 12:05:00 ERROR Database timeout\n")
            f.write("2024-01-01 12:05:05 ERROR Another Database timeout error\n")
            f.write("2024-01-01 12:08:00 INFO API /users/profile took 250ms\n")
            f.write("2024-01-01 12:09:00 WARN Memory usage at 87%\n")
            f.write("2024-01-01 12:10:00 INFO API /data/fetch took 120ms\n")
            f.write("2024-01-01 12:11:00 INFO User 42 logged out\n")
            f.write("2024-01-01 12:12:00 INFO User 101 logged in\n")
            f.write("2024-01-01 12:15:00 INFO API /status took 50ms\n")
    main()
