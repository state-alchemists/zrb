import datetime
import os
import re
import sqlite3
from typing import Dict, List, Tuple, Set

# Configuration using environment variables
DB_PATH: str = os.environ.get("DB_PATH", "metrics.db")
LOG_FILE: str = os.environ.get("LOG_FILE", "server.log")
DB_HOST: str = os.environ.get("DB_HOST", "localhost")
DB_PORT: int = int(os.environ.get("DB_PORT", "5432"))
DB_USER: str = os.environ.get("DB_USER", "admin")
DB_PASS: str = os.environ.get("DB_PASS", "password123")

# Regular expressions for log parsing
LOG_PATTERN = re.compile(r"^(?P<date>\d{4}-\d{2}-\d{2}) (?P<time>\d{2}:\d{2}:\d{2}) (?P<level>\w+) (?P<message>.*)$")
USER_PATTERN = re.compile(r"^User (?P<uid>\S+)\s+(?P<action>.*)$")
API_PATTERN = re.compile(r"^API (?P<endpoint>\S+)(?:.*took (?P<duration>\d+)ms)?.*$")


def extract_logs(file_path: str) -> List[str]:
    """
    Extract log lines from the given file path.
    
    :param file_path: Path to the log file.
    :return: List of log lines.
    """
    if not os.path.exists(file_path):
        return []
    with open(file_path, "r", encoding="utf-8") as f:
        return f.readlines()


def transform_logs(log_lines: List[str]) -> Tuple[Dict[str, int], Dict[str, List[int]], int]:
    """
    Parse log lines and aggregate metrics.
    
    :param log_lines: List of raw log string lines.
    :return: A tuple containing:
             - Dictionary of error messages and their counts.
             - Dictionary of API endpoints and lists of their latency times.
             - Integer count of currently active sessions.
    """
    errors: Dict[str, int] = {}
    api_metrics: Dict[str, List[int]] = {}
    active_sessions: Set[str] = set()

    for line in log_lines:
        match = LOG_PATTERN.match(line.strip())
        if not match:
            continue
            
        level = match.group("level")
        message = match.group("message")
        
        if level == "ERROR":
            errors[message] = errors.get(message, 0) + 1
            
        elif level == "INFO":
            user_match = USER_PATTERN.match(message)
            if user_match:
                uid = user_match.group("uid")
                action = user_match.group("action")
                if "logged in" in action:
                    active_sessions.add(uid)
                elif "logged out" in action:
                    active_sessions.discard(uid)
                continue
                
            api_match = API_PATTERN.match(message)
            if api_match:
                endpoint = api_match.group("endpoint")
                duration_str = api_match.group("duration")
                duration = int(duration_str) if duration_str else 0
                api_metrics.setdefault(endpoint, []).append(duration)
                
    return errors, api_metrics, len(active_sessions)


def load_to_db(errors: Dict[str, int], api_metrics: Dict[str, List[int]]) -> None:
    """
    Load aggregated metrics into the SQLite database.
    
    :param errors: Dictionary of error messages and their counts.
    :param api_metrics: Dictionary of API endpoints and latency lists.
    """
    print(f"Connecting to {DB_HOST}:{DB_PORT} as {DB_USER}...")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("CREATE TABLE IF NOT EXISTS errors (dt TEXT, message TEXT, count INTEGER)")
    cursor.execute("CREATE TABLE IF NOT EXISTS api_metrics (dt TEXT, endpoint TEXT, avg_ms REAL)")
    
    now = str(datetime.datetime.now())
    
    # Insert errors using parameterized query
    for msg, count in errors.items():
        cursor.execute(
            "INSERT INTO errors (dt, message, count) VALUES (?, ?, ?)",
            (now, msg, count)
        )
        
    # Insert API metrics using parameterized query
    for endpoint, times in api_metrics.items():
        if times:
            avg_ms = sum(times) / len(times)
            cursor.execute(
                "INSERT INTO api_metrics (dt, endpoint, avg_ms) VALUES (?, ?, ?)",
                (now, endpoint, avg_ms)
            )
            
    conn.commit()
    conn.close()


def generate_report(errors: Dict[str, int], api_metrics: Dict[str, List[int]], active_session_count: int, output_path: str = "report.html") -> None:
    """
    Generate an HTML report with the processed metrics.
    
    :param errors: Dictionary of error messages and their counts.
    :param api_metrics: Dictionary of API endpoints and latency lists.
    :param active_session_count: Number of currently active sessions.
    :param output_path: Path to write the HTML report.
    """
    html = ["<html>\n<head><title>System Report</title></head>\n<body>\n"]
    
    html.append("<h1>Error Summary</h1>\n<ul>\n")
    for msg, count in errors.items():
        html.append(f"<li><b>{msg}</b>: {count} occurrences</li>\n")
    html.append("</ul>\n")
    
    html.append("<h2>API Latency</h2>\n<table border='1'>\n")
    html.append("<tr><th>Endpoint</th><th>Avg (ms)</th></tr>\n")
    for endpoint, times in api_metrics.items():
        if times:
            avg = sum(times) / len(times)
            html.append(f"<tr><td>{endpoint}</td><td>{round(avg, 1)}</td></tr>\n")
    html.append("</table>\n")
    
    html.append("<h2>Active Sessions</h2>\n")
    html.append(f"<p>{active_session_count} user(s) currently active</p>\n")
    
    html.append("</body>\n</html>")
    
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("".join(html))


def run_pipeline() -> None:
    """
    Execute the ETL pipeline and generate the report.
    """
    log_lines = extract_logs(LOG_FILE)
    errors, api_metrics, active_session_count = transform_logs(log_lines)
    
    load_to_db(errors, api_metrics)
    generate_report(errors, api_metrics, active_session_count)
    
    print(f"Job finished at {datetime.datetime.now()}")


if __name__ == "__main__":
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, "w", encoding="utf-8") as f:
            f.write("2024-01-01 12:00:00 INFO User 42 logged in\n")
            f.write("2024-01-01 12:05:00 ERROR Database timeout\n")
            f.write("2024-01-01 12:05:05 ERROR Database timeout\n")
            f.write("2024-01-01 12:08:00 INFO API /users/profile took 250ms\n")
            f.write("2024-01-01 12:09:00 WARN Memory usage at 87%\n")
            f.write("2024-01-01 12:10:00 INFO User 42 logged out\n")
    run_pipeline()
