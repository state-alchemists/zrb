import datetime
import os
import re
import sqlite3
from typing import Dict, List, Tuple

# Environment configurations with defaults
DB_PATH = os.getenv("DB_PATH", "metrics.db")
LOG_FILE = os.getenv("LOG_FILE", "server.log")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_USER = os.getenv("DB_USER", "admin")
DB_PASS = os.getenv("DB_PASS", "password123")

# Regular expressions for log parsing
LOG_PATTERN = re.compile(
    r"^(?P<date>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s+(?P<level>\w+)\s+(?P<message>.*)$"
)
USER_PATTERN = re.compile(r"^User (?P<uid>\S+) (?P<action>.*)$")
API_PATTERN = re.compile(r"^API (?P<endpoint>\S+) took (?P<ms>\d+)ms$")


def extract_logs(log_file: str) -> List[Dict[str, str]]:
    """
    Extracts raw log lines from the given log file and parses basic structures.

    Args:
        log_file: Path to the log file.

    Returns:
        A list of dictionaries, each containing 'date', 'level', and 'message' keys.
    """
    parsed_logs = []
    if not os.path.exists(log_file):
        return parsed_logs

    with open(log_file, "r") as f:
        for line in f:
            match = LOG_PATTERN.match(line.strip())
            if match:
                parsed_logs.append(match.groupdict())

    return parsed_logs


def transform_data(raw_logs: List[Dict[str, str]]) -> Tuple[Dict[str, int], Dict[str, float], int]:
    """
    Transforms raw logs into aggregated metrics.

    Args:
        raw_logs: List of parsed log entries.

    Returns:
        A tuple containing:
        - Dictionary of error messages to their occurrence count
        - Dictionary of API endpoints to their average latency in ms
        - Integer representing the count of currently active sessions
    """
    errors: Dict[str, int] = {}
    sessions: Dict[str, str] = {}
    api_calls: Dict[str, List[int]] = {}

    for log in raw_logs:
        lvl = log["level"]
        msg = log["message"]
        dt = log["date"]

        if lvl == "ERROR":
            errors[msg] = errors.get(msg, 0) + 1

        elif lvl == "INFO":
            user_match = USER_PATTERN.match(msg)
            if user_match:
                uid = user_match.group("uid")
                action = user_match.group("action")
                if "logged in" in action:
                    sessions[uid] = dt
                elif "logged out" in action and uid in sessions:
                    sessions.pop(uid)
                continue

            api_match = API_PATTERN.match(msg)
            if api_match:
                endpoint = api_match.group("endpoint")
                ms = int(api_match.group("ms"))
                api_calls.setdefault(endpoint, []).append(ms)

    avg_api_latency: Dict[str, float] = {}
    for ep, times in api_calls.items():
        avg_api_latency[ep] = sum(times) / len(times)

    return errors, avg_api_latency, len(sessions)


def load_data_to_db(errors: Dict[str, int], api_metrics: Dict[str, float], db_path: str) -> None:
    """
    Loads transformed metrics into the database securely using parameterized queries.

    Args:
        errors: Dictionary mapping error messages to their counts.
        api_metrics: Dictionary mapping API endpoints to their average latency.
        db_path: Path to the SQLite database.
    """
    print(f"Connecting to {DB_HOST}:{DB_PORT} as {DB_USER}...")

    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS errors (dt TEXT, message TEXT, count INTEGER)")
    c.execute("CREATE TABLE IF NOT EXISTS api_metrics (dt TEXT, endpoint TEXT, avg_ms REAL)")

    now = datetime.datetime.now().isoformat()

    # Fixed SQL Injection: Using parameterized queries (?) instead of string formatting
    for msg, count in errors.items():
        c.execute(
            "INSERT INTO errors (dt, message, count) VALUES (?, ?, ?)",
            (now, msg, count),
        )

    for ep, avg in api_metrics.items():
        c.execute(
            "INSERT INTO api_metrics (dt, endpoint, avg_ms) VALUES (?, ?, ?)",
            (now, ep, avg),
        )

    conn.commit()
    conn.close()


def generate_html_report(
    errors: Dict[str, int], api_metrics: Dict[str, float], active_sessions: int, output_file: str = "report.html"
) -> None:
    """
    Generates an HTML report summarizing errors, API latencies, and active sessions.

    Args:
        errors: Dictionary mapping error messages to their counts.
        api_metrics: Dictionary mapping API endpoints to their average latency.
        active_sessions: Number of active sessions.
        output_file: The path where the HTML report will be saved.
    """
    out = "<html>\n<head><title>System Report</title></head>\n<body>\n"
    out += "<h1>Error Summary</h1>\n<ul>\n"
    for err_msg, count in errors.items():
        out += f"<li><b>{err_msg}</b>: {count} occurrences</li>\n"
    out += "</ul>\n"

    out += "<h2>API Latency</h2>\n<table border='1'>\n"
    out += "<tr><th>Endpoint</th><th>Avg (ms)</th></tr>\n"
    for ep, avg in api_metrics.items():
        out += f"<tr><td>{ep}</td><td>{round(avg, 1)}</td></tr>\n"
    out += "</table>\n"

    out += "<h2>Active Sessions</h2>\n"
    out += f"<p>{active_sessions} user(s) currently active</p>\n"
    out += "</body>\n</html>"

    with open(output_file, "w") as f:
        f.write(out)

    print(f"Job finished at {datetime.datetime.now()}")


def run_pipeline() -> None:
    """
    Orchestrates the ETL pipeline: extracts logs, transforms data, loads into DB, and generates a report.
    """
    raw_logs = extract_logs(LOG_FILE)
    errors, api_metrics, active_sessions = transform_data(raw_logs)
    load_data_to_db(errors, api_metrics, DB_PATH)
    generate_html_report(errors, api_metrics, active_sessions)


if __name__ == "__main__":
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, "w") as f:
            f.write("2024-01-01 12:00:00 INFO User 42 logged in\n")
            f.write("2024-01-01 12:05:00 ERROR Database timeout\n")
            f.write("2024-01-01 12:05:05 ERROR Database timeout\n")
            f.write("2024-01-01 12:08:00 INFO API /users/profile took 250ms\n")
            f.write("2024-01-01 12:09:00 WARN Memory usage at 87%\n")
            f.write("2024-01-01 12:10:00 INFO User 42 logged out\n")
    run_pipeline()
