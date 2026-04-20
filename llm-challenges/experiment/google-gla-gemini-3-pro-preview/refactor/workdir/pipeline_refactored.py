import datetime
import os
import sqlite3
import re
from typing import List, Dict, Tuple, Any

# Configuration from environment variables with sensible defaults
DB_PATH = os.environ.get("DB_PATH", "metrics.db")
LOG_FILE = os.environ.get("LOG_FILE", "server.log")
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = int(os.environ.get("DB_PORT", "5432"))
DB_USER = os.environ.get("DB_USER", "admin")
DB_PASS = os.environ.get("DB_PASS", "password123")

# Regex patterns for log parsing
LOG_PATTERN = re.compile(
    r"^(?P<date>\d{4}-\d{2}-\d{2})\s+(?P<time>\d{2}:\d{2}:\d{2})\s+(?P<level>[A-Z]+)\s+(?P<message>.*)$"
)
USER_PATTERN = re.compile(r"^User\s+(?P<uid>\S+)\s+(?P<action>.*)$")
API_PATTERN = re.compile(r"^API\s+(?P<endpoint>\S+)(?:\s+took\s+(?P<ms>\d+)ms)?$")


def extract_logs(log_file: str) -> List[Dict[str, str]]:
    """
    Extracts and parses logs from the specified log file using regular expressions.
    """
    parsed_logs = []
    if not os.path.exists(log_file):
        return parsed_logs
        
    with open(log_file, "r") as f:
        for line in f:
            match = LOG_PATTERN.match(line.strip())
            if match:
                log_data = match.groupdict()
                log_data["dt"] = f"{log_data['date']} {log_data['time']}"
                parsed_logs.append(log_data)
                
    return parsed_logs


def transform_logs(logs: List[Dict[str, str]]) -> Tuple[Dict[str, int], Dict[str, List[int]], int]:
    """
    Transforms parsed logs into actionable metrics:
    - Counts of error messages
    - Lists of latency values per API endpoint
    - The number of currently active sessions
    """
    errors: Dict[str, int] = {}
    api_stats: Dict[str, List[int]] = {}
    sessions: Dict[str, str] = {}
    
    for log in logs:
        level = log["level"]
        message = log["message"]
        dt = log["dt"]
        
        if level == "ERROR":
            errors[message] = errors.get(message, 0) + 1
            
        elif level == "INFO":
            user_match = USER_PATTERN.match(message)
            if user_match:
                uid = user_match.group("uid")
                action = user_match.group("action")
                if "logged in" in action:
                    sessions[uid] = dt
                elif "logged out" in action and uid in sessions:
                    sessions.pop(uid)
                continue
                
            api_match = API_PATTERN.match(message)
            if api_match:
                endpoint = api_match.group("endpoint")
                ms = int(api_match.group("ms")) if api_match.group("ms") else 0
                api_stats.setdefault(endpoint, []).append(ms)
                
    return errors, api_stats, len(sessions)


def load_to_database(db_path: str, errors: Dict[str, int], api_stats: Dict[str, List[int]]) -> Dict[str, float]:
    """
    Loads error counts and API metrics into the SQLite database.
    Uses parameterized queries to prevent SQL injection.
    Returns the computed average latency per API endpoint.
    """
    print(f"Connecting to {DB_HOST}:{DB_PORT} as {DB_USER}...")
    
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS errors (dt TEXT, message TEXT, count INTEGER)")
    c.execute("CREATE TABLE IF NOT EXISTS api_metrics (dt TEXT, endpoint TEXT, avg_ms REAL)")
    
    now = str(datetime.datetime.now())
    
    # Load errors
    for msg, count in errors.items():
        c.execute(
            "INSERT INTO errors VALUES (?, ?, ?)",
            (now, msg, count)
        )
        
    # Calculate averages and load api metrics
    avg_api_stats: Dict[str, float] = {}
    for ep, times in api_stats.items():
        avg = sum(times) / len(times) if times else 0.0
        avg_api_stats[ep] = avg
        c.execute(
            "INSERT INTO api_metrics VALUES (?, ?, ?)",
            (now, ep, avg)
        )
        
    conn.commit()
    conn.close()
    
    return avg_api_stats


def generate_report(errors: Dict[str, int], avg_api_stats: Dict[str, float], active_sessions_count: int, output_file: str = "report.html") -> None:
    """
    Generates an HTML report summarizing errors, API latency, and active sessions.
    """
    out = "<html>\n<head><title>System Report</title></head>\n<body>\n"
    out += "<h1>Error Summary</h1>\n<ul>\n"
    for err_msg, count in errors.items():
        out += f"<li><b>{err_msg}</b>: {count} occurrences</li>\n"
    out += "</ul>\n"

    out += "<h2>API Latency</h2>\n<table border='1'>\n"
    out += "<tr><th>Endpoint</th><th>Avg (ms)</th></tr>\n"
    for ep, avg in avg_api_stats.items():
        out += f"<tr><td>{ep}</td><td>{round(avg, 1)}</td></tr>\n"
    out += "</table>\n"

    out += "<h2>Active Sessions</h2>\n"
    out += f"<p>{active_sessions_count} user(s) currently active</p>\n"
    out += "</body>\n</html>"

    with open(output_file, "w") as f:
        f.write(out)


def proc_data() -> None:
    """
    Main ETL pipeline. Extracts logs, transforms into metrics,
    loads them into the database, and generates the final HTML report.
    """
    logs = extract_logs(LOG_FILE)
    errors, api_stats, active_sessions_count = transform_logs(logs)
    avg_api_stats = load_to_database(DB_PATH, errors, api_stats)
    generate_report(errors, avg_api_stats, active_sessions_count)
    
    print(f"Job finished at {datetime.datetime.now()}")


if __name__ == "__main__":
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, "w") as f:
            f.write("2024-01-01 12:00:00 INFO User 42 logged in\n")
            f.write("2024-01-01 12:05:00 ERROR Database timeout\n")
            f.write("2024-01-01 12:05:05 ERROR Database timeout\n")
            f.write("2024-01-01 12:08:00 INFO API /users/profile took 250ms\n")
            f.write("2024-01-01 12:09:00 WARN Memory usage at 87%\n")
            f.write("2024-01-01 12:10:00 INFO User 42 logged out\n")
    proc_data()
