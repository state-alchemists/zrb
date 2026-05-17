import datetime
import os
import sqlite3
import re
from typing import Dict, List, Tuple, Set


def extract_logs(log_file: str) -> List[str]:
    """
    Reads log lines from the specified file.

    Args:
        log_file: Path to the log file.

    Returns:
        A list of strings, each representing a line from the log file.
    """
    if not os.path.exists(log_file):
        return []
    with open(log_file, "r") as f:
        return f.readlines()


def transform_logs(log_lines: List[str]) -> Tuple[Dict[str, int], Dict[str, float], int]:
    """
    Parses log lines using regex and aggregates metrics for errors, API calls, and sessions.

    Args:
        log_lines: A list of raw log strings.

    Returns:
        A tuple containing:
        - Dictionary mapping error messages to their occurrence counts.
        - Dictionary mapping API endpoints to their average latency in milliseconds.
        - Integer count of currently active user sessions.
    """
    error_counts: Dict[str, int] = {}
    api_calls: Dict[str, List[int]] = {}
    active_sessions: Set[str] = set()

    # Regex patterns for parsing logs
    log_pattern = re.compile(
        r"^(?P<date>\d{4}-\d{2}-\d{2})\s+"
        r"(?P<time>\d{2}:\d{2}:\d{2})\s+"
        r"(?P<level>[A-Z]+)\s+"
        r"(?P<message>.*)$"
    )
    user_pattern = re.compile(r"^User\s+(?P<uid>\S+)\s+(?P<action>.*)$")
    api_pattern = re.compile(r"^API\s+(?P<endpoint>\S+).*?(?:took\s+(?P<ms>\d+)ms)?$")

    for line in log_lines:
        match = log_pattern.match(line.strip())
        if not match:
            continue

        level = match.group("level")
        message = match.group("message")

        if level == "ERROR":
            error_counts[message] = error_counts.get(message, 0) + 1
        elif level == "INFO":
            user_match = user_pattern.match(message)
            if user_match:
                uid = user_match.group("uid")
                action = user_match.group("action")
                if "logged in" in action:
                    active_sessions.add(uid)
                elif "logged out" in action:
                    active_sessions.discard(uid)
                continue

            api_match = api_pattern.match(message)
            if api_match:
                endpoint = api_match.group("endpoint")
                ms_str = api_match.group("ms")
                ms = int(ms_str) if ms_str else 0
                api_calls.setdefault(endpoint, []).append(ms)

    # Calculate average API latencies
    api_averages = {
        ep: sum(times) / len(times) for ep, times in api_calls.items() if times
    }

    return error_counts, api_averages, len(active_sessions)


def load_to_db(db_path: str, error_counts: Dict[str, int], api_averages: Dict[str, float]) -> None:
    """
    Saves aggregated error counts and API metrics to the SQLite database.
    Uses parameterized queries to prevent SQL injection.

    Args:
        db_path: Path to the SQLite database file.
        error_counts: Dictionary of error messages and their counts.
        api_averages: Dictionary of API endpoints and their average latencies.
    """
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS errors (dt TEXT, message TEXT, count INTEGER)")
    c.execute("CREATE TABLE IF NOT EXISTS api_metrics (dt TEXT, endpoint TEXT, avg_ms REAL)")

    now = datetime.datetime.now().isoformat()

    # Parameterized queries
    error_data = [(now, msg, count) for msg, count in error_counts.items()]
    c.executemany("INSERT INTO errors VALUES (?, ?, ?)", error_data)

    api_data = [(now, ep, avg) for ep, avg in api_averages.items()]
    c.executemany("INSERT INTO api_metrics VALUES (?, ?, ?)", api_data)

    conn.commit()
    conn.close()


def generate_report(error_counts: Dict[str, int], api_averages: Dict[str, float], active_sessions_count: int) -> str:
    """
    Generates an HTML report string based on the provided metrics.

    Args:
        error_counts: Dictionary of error messages and their counts.
        api_averages: Dictionary of API endpoints and their average latencies.
        active_sessions_count: Number of currently active user sessions.

    Returns:
        A formatted HTML string representing the system report.
    """
    out = "<html>\n<head><title>System Report</title></head>\n<body>\n"
    out += "<h1>Error Summary</h1>\n<ul>\n"
    for err_msg, count in error_counts.items():
        out += f"<li><b>{err_msg}</b>: {count} occurrences</li>\n"
    out += "</ul>\n"

    out += "<h2>API Latency</h2>\n<table border='1'>\n"
    out += "<tr><th>Endpoint</th><th>Avg (ms)</th></tr>\n"
    for ep, avg in api_averages.items():
        out += f"<tr><td>{ep}</td><td>{round(avg, 1)}</td></tr>\n"
    out += "</table>\n"

    out += "<h2>Active Sessions</h2>\n"
    out += f"<p>{active_sessions_count} user(s) currently active</p>\n"
    out += "</body>\n</html>"

    return out


def main() -> None:
    """
    Main execution flow for the ETL log pipeline.
    Reads configuration from environment variables, processes logs,
    loads metrics to a database, and generates an HTML report.
    """
    db_path = os.getenv("DB_PATH", "metrics.db")
    log_file = os.getenv("LOG_FILE", "server.log")
    db_host = os.getenv("DB_HOST", "localhost")
    db_port = os.getenv("DB_PORT", "5432")
    db_user = os.getenv("DB_USER", "admin")
    # DB_PASS is intentionally unused here, matching original script behavior
    _db_pass = os.getenv("DB_PASS", "password123")

    log_lines = extract_logs(log_file)
    error_counts, api_averages, active_sessions_count = transform_logs(log_lines)

    # Mimic original script output
    print(f"Connecting to {db_host}:{db_port} as {db_user}...")

    load_to_db(db_path, error_counts, api_averages)

    report_html = generate_report(error_counts, api_averages, active_sessions_count)
    with open("report.html", "w") as f:
        f.write(report_html)

    print(f"Job finished at {datetime.datetime.now()}")


if __name__ == "__main__":
    # Create a dummy log file if one doesn't exist for immediate execution testing
    test_log_file = os.getenv("LOG_FILE", "server.log")
    if not os.path.exists(test_log_file):
        with open(test_log_file, "w") as f:
            f.write("2024-01-01 12:00:00 INFO User 42 logged in\n")
            f.write("2024-01-01 12:05:00 ERROR Database timeout\n")
            f.write("2024-01-01 12:05:05 ERROR Database timeout\n")
            f.write("2024-01-01 12:08:00 INFO API /users/profile took 250ms\n")
            f.write("2024-01-01 12:09:00 WARN Memory usage at 87%\n")
            f.write("2024-01-01 12:10:00 INFO User 42 logged out\n")
    
    main()
