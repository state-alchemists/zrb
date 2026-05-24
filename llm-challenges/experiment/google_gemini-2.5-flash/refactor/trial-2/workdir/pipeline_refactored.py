import datetime
import os
import re
import sqlite3
from typing import Dict, List, Any, Tuple

# --- Configuration ---
def load_config() -> Dict[str, str]:
    """Loads configuration from environment variables."""
    config = {
        "DB_PATH": os.getenv("DB_PATH", "metrics.db"),
        "LOG_FILE": os.getenv("LOG_FILE", "server.log"),

        "REPORT_FILE": os.getenv("REPORT_FILE", "report.html")
    }
    return config

# --- Extraction ---
def parse_log_line(line: str) -> Dict[str, Any] | None:
    """Parses a single log line using regex and extracts relevant data.

    Args:
        line: The log line string.

    Returns:
        A dictionary containing parsed data (dt, lvl, msg, etc.), or None if the line
        does not match expected patterns.
    """
    # Regex to capture timestamp, level, and the rest of the message
    match = re.match(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) (INFO|ERROR|WARN) (.*)$", line)
    if not match:
        return None

    dt, lvl, message = match.groups()
    parsed_data: Dict[str, Any] = {"dt": dt, "lvl": lvl}

    if lvl == "ERROR":
        parsed_data["type"] = "ERR"
        parsed_data["message"] = message.strip()
    elif lvl == "INFO":
        user_match = re.match(r"^User (\d+) (logged in|logged out)", message)
        if user_match:
            uid, action = user_match.groups()
            parsed_data["type"] = "USR"
            parsed_data["uid"] = uid
            parsed_data["action"] = action.strip()
        else:
            return None
    elif "API" in message:
        if re.match(r"^API ([/\w]+) took (\d+)ms$", message):
            api_match = re.match(r"^API ([/\w]+) took (\d+)ms$", message)
            endpoint, duration_ms = api_match.groups()
            parsed_data["type"] = "API"
            parsed_data["endpoint"] = endpoint
            parsed_data["ms"] = int(duration_ms)
        elif re.match(r"^API ([/\w]+)$", message):
            api_match_no_duration = re.match(r"^API ([/\w]+)$", message)
            endpoint = api_match_no_duration.groups()[0]
            parsed_data["type"] = "API"
            parsed_data["endpoint"] = endpoint
            parsed_data["ms"] = 0
        else:
            return None
        else: # Unhandled INFO message
            return None
    elif lvl == "WARN":
        parsed_data["type"] = "WARN"
        parsed_data["message"] = message.strip()
    else:
        return None # Unhandled log level

    return parsed_data


def extract_log_data(log_file_path: str) -> Tuple[List[Dict[str, Any]], Dict[str, str], List[Dict[str, Any]]]:
    """Reads a log file, parses each line, and categorizes the extracted data.

    Args:
        log_file_path: The path to the server log file.

    Returns:
        A tuple containing:
        - A list of all parsed events (errors, warnings, user actions, API calls).
        - A dictionary of active user sessions (uid -> login_timestamp).
        - A list of raw API call events.
    """
    all_events: List[Dict[str, Any]] = []
    active_sessions: Dict[str, str] = {}
    api_call_events: List[Dict[str, Any]] = []

    if not os.path.exists(log_file_path):
        print(f"Log file not found: {log_file_path}")
        return [], {}, []

    with open(log_file_path, "r") as f:
        for line in f:
            parsed = parse_log_line(line)
            if parsed:
                all_events.append(parsed)
                if parsed.get("type") == "USR":
                    uid = parsed["uid"]
                    action = parsed["action"]
                    dt = parsed["dt"]
                    if "logged in" in action:
                        active_sessions[uid] = dt
                    elif "logged out" in action and uid in active_sessions:
                        active_sessions.pop(uid)
                elif parsed.get("type") == "API":
                    api_call_events.append(parsed)
    return all_events, active_sessions, api_call_events

# --- Transformation ---
def summarize_errors(events: List[Dict[str, Any]]) -> Dict[str, int]:
    """Summarizes error messages and their counts from parsed events.

    Args:
        events: A list of all parsed log events.

    Returns:
        A dictionary where keys are error messages and values are their counts.
    """
    error_summary: Dict[str, int] = {}
    for event in events:
        if event.get("type") == "ERR":
            msg = event["message"]
            error_summary[msg] = error_summary.get(msg, 0) + 1
    return error_summary

def analyze_api_latency(api_calls: List[Dict[str, Any]]) -> Dict[str, float]:
    """Calculates the average latency for each API endpoint.

    Args:
        api_calls: A list of parsed API call events.

    Returns:
        A dictionary where keys are API endpoints and values are their average
        latency in milliseconds.
    """
    endpoint_times: Dict[str, List[int]] = {}
    for call in api_calls:
        endpoint = call["endpoint"]
        endpoint_times.setdefault(endpoint, []).append(call["ms"])

    api_latency_summary: Dict[str, float] = {}
    for ep, times in endpoint_times.items():
        api_latency_summary[ep] = sum(times) / len(times)
    return api_latency_summary

# --- Loading ---
def connect_db(db_path: str) -> sqlite3.Connection:
    """Establishes a connection to the SQLite database.

    Args:
        db_path: The path to the SQLite database file.

    Returns:
        A sqlite3 Connection object.
    """
    print(f"Connecting to SQLite database: {db_path}...")
    return sqlite3.connect(db_path)

def initialize_db_schema(conn: sqlite3.Connection) -> None:
    """Creates database tables if they do not already exist.

    Args:
        conn: The database connection object.
    """
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS errors (dt TEXT, message TEXT, count INTEGER)")
    c.execute("CREATE TABLE IF NOT EXISTS api_metrics (dt TEXT, endpoint TEXT, avg_ms REAL)")
    conn.commit()

def insert_error_summary(conn: sqlite3.Connection, error_summary: Dict[str, int]) -> None:
    """Inserts error summary data into the 'errors' table using parameterized queries.

    Args:
        conn: The database connection object.
        error_summary: A dictionary of error messages and their counts.
    """
    c = conn.cursor()
    now = datetime.datetime.now().isoformat()
    for msg, count in error_summary.items():
        c.execute("INSERT INTO errors VALUES (?, ?, ?)", (now, msg, count))
    conn.commit()

def insert_api_latency(conn: sqlite3.Connection, api_latency_summary: Dict[str, float]) -> None:
    """Inserts API latency data into the 'api_metrics' table using parameterized queries.

    Args:
        conn: The database connection object.
        api_latency_summary: A dictionary of API endpoints and their average latencies.
    """
    c = conn.cursor()
    now = datetime.datetime.now().isoformat()
    for ep, avg in api_latency_summary.items():
        c.execute("INSERT INTO api_metrics VALUES (?, ?, ?)", (now, ep, avg))
    conn.commit()

def generate_html_report(
    error_summary: Dict[str, int],
    api_latency_summary: Dict[str, float],
    active_session_count: int,
    report_file_path: str
) -> None:
    """Generates an HTML report file with error summary, API latency, and active sessions.

    Args:
        error_summary: Summary of error messages and counts.
        api_latency_summary: Summary of API endpoint latencies.
        active_session_count: The number of currently active user sessions.
        report_file_path: The path where the HTML report will be saved.
    """
    lines = []
    lines.append("<html>")
    lines.append("<head><title>System Report</title></head>")
    lines.append("<body>")
    lines.append("<h1>Error Summary</h1>")
    lines.append("<ul>")
    for err_msg, count in error_summary.items():
        lines.append(f"<li><b>{err_msg}</b>: {count} occurrences</li>")
    lines.append("</ul>")

    lines.append("<h2>API Latency</h2>")
    lines.append("<table border='1'>")
    lines.append("<tr><th>Endpoint</th><th>Avg (ms)</th></tr>")
    for ep, avg in api_latency_summary.items():
        lines.append(f"<tr><td>{ep}</td><td>{round(avg, 1)}</td></tr>")
    lines.append("</table>")

    lines.append("<h2>Active Sessions</h2>")
    lines.append(f"<p>{active_session_count} user(s) currently active</p>")
    lines.append("</body>")
    lines.append("</html>")
    out = "\n".join(lines)

    with open(report_file_path, "w") as f:
        f.write(out)
    print(f"Report generated at {report_file_path}")

# --- Main Orchestration ---
def main():
    """Main function to orchestrate the log processing and report generation."""
    config = load_config()
    db_path = config["DB_PATH"]
    log_file = config["LOG_FILE"]
    report_file = config["REPORT_FILE"]

    # For demonstration: create a dummy log file if it doesn't exist
    if not os.path.exists(log_file):
        with open(log_file, "w") as f:
            f.write("2024-01-01 12:00:00 INFO User 42 logged in\n")
            f.write("2024-01-01 12:05:00 ERROR Database timeout\n")
            f.write("2024-01-01 12:05:05 ERROR Database timeout\n")
            f.write("2024-01-01 12:08:00 INFO API /users/profile took 250ms\n")
            f.write("2024-01-01 12:09:00 WARN Memory usage at 87%\n")
            f.write("2024-01-01 12:10:00 INFO User 42 logged out\n")
            f.write("2024-01-01 12:11:00 INFO API /health no duration\n")


    print(f"Processing logs from {log_file}...")
    all_events, active_sessions, api_calls = extract_log_data(log_file)
    print(f"Extracted {len(all_events)} events, {len(active_sessions)} active sessions, {len(api_calls)} api calls.")
    error_summary = summarize_errors(all_events)
    print(f"Error summary: {error_summary}")
    api_latency_summary = analyze_api_latency(api_calls)
    print(f"API latency summary: {api_latency_summary}")

    conn = None
    try:
        conn = connect_db(db_path)
        initialize_db_schema(conn)
        insert_error_summary(conn, error_summary)
        insert_api_latency(conn, api_latency_summary)
    finally:
        if conn:
            conn.close()

    generate_html_report(
        error_summary,
        api_latency_summary,
        len(active_sessions),
        report_file
    )

    print(f"Job finished at {datetime.datetime.now()}")


if __name__ == "__main__":
    main()
