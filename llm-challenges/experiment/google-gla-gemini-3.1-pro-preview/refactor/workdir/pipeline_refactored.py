import datetime
import os
import re
import sqlite3
from typing import List, Dict, Any, Tuple

# Configuration from environment variables
DB_PATH = os.getenv("DB_PATH", "metrics.db")
LOG_FILE = os.getenv("LOG_FILE", "server.log")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_USER = os.getenv("DB_USER", "admin")
DB_PASS = os.getenv("DB_PASS", "password123")

# Pre-compile regex patterns
LOG_PATTERN = re.compile(r"^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s+(?P<level>\w+)\s+(?P<message>.*)$")
USER_PATTERN = re.compile(r"^User\s+(?P<uid>\S+)\s+(?P<action>.*)$")
API_PATTERN = re.compile(r"^API\s+(?P<endpoint>\S+)\s+took\s+(?P<ms>\d+)ms$")


def extract_logs(log_file: str) -> List[Dict[str, Any]]:
    """
    Extracts and parses log entries from the specified file using regex.

    Args:
        log_file: Path to the log file.

    Returns:
        A list of parsed log dictionaries containing level, timestamp, and specific event data.
    """
    parsed_logs = []
    if not os.path.exists(log_file):
        return parsed_logs

    with open(log_file, "r") as f:
        for line in f:
            match = LOG_PATTERN.match(line.strip())
            if not match:
                continue
            
            timestamp = match.group("timestamp")
            level = match.group("level")
            message = match.group("message")
            
            log_entry = {"timestamp": timestamp, "level": level}
            
            if level == "ERROR":
                log_entry["type"] = "ERR"
                log_entry["message"] = message
                parsed_logs.append(log_entry)
            elif level == "WARN":
                log_entry["type"] = "WARN"
                log_entry["message"] = message
                parsed_logs.append(log_entry)
            elif level == "INFO":
                user_match = USER_PATTERN.match(message)
                if user_match:
                    log_entry["type"] = "USR"
                    log_entry["uid"] = user_match.group("uid")
                    log_entry["action"] = user_match.group("action")
                    parsed_logs.append(log_entry)
                    continue
                
                api_match = API_PATTERN.match(message)
                if api_match:
                    log_entry["type"] = "API"
                    log_entry["endpoint"] = api_match.group("endpoint")
                    log_entry["ms"] = int(api_match.group("ms"))
                    parsed_logs.append(log_entry)
                    continue

    return parsed_logs


def transform_data(logs: List[Dict[str, Any]]) -> Tuple[Dict[str, int], Dict[str, float], int]:
    """
    Transforms raw logs into aggregated metrics: error counts, API latencies, and active sessions.

    Args:
        logs: A list of parsed log dictionaries.

    Returns:
        A tuple containing:
        - Dictionary of error messages to their occurrence counts.
        - Dictionary of API endpoints to their average latency in ms.
        - Integer representing the current number of active user sessions.
    """
    error_counts: Dict[str, int] = {}
    api_calls: Dict[str, List[int]] = {}
    active_sessions: Dict[str, str] = {}

    for log in logs:
        if log.get("type") == "ERR":
            msg = log["message"]
            error_counts[msg] = error_counts.get(msg, 0) + 1
            
        elif log.get("type") == "USR":
            uid = log["uid"]
            action = log["action"]
            if "logged in" in action:
                active_sessions[uid] = log["timestamp"]
            elif "logged out" in action and uid in active_sessions:
                active_sessions.pop(uid)
                
        elif log.get("type") == "API":
            ep = log["endpoint"]
            api_calls.setdefault(ep, []).append(log["ms"])

    api_avg_latencies = {
        ep: sum(times) / len(times)
        for ep, times in api_calls.items()
        if times
    }

    return error_counts, api_avg_latencies, len(active_sessions)


def load_to_db(db_path: str, errors: Dict[str, int], api_latencies: Dict[str, float]) -> None:
    """
    Loads aggregated error and API latency metrics into a SQLite database.
    Uses parameterized queries to prevent SQL injection.

    Args:
        db_path: Path to the SQLite database file.
        errors: Dictionary of error messages and counts.
        api_latencies: Dictionary of API endpoints and average latencies.
    """
    print(f"Connecting to {DB_HOST}:{DB_PORT} as {DB_USER}...")
    
    with sqlite3.connect(db_path) as conn:
        c = conn.cursor()
        c.execute("CREATE TABLE IF NOT EXISTS errors (dt TEXT, message TEXT, count INTEGER)")
        c.execute("CREATE TABLE IF NOT EXISTS api_metrics (dt TEXT, endpoint TEXT, avg_ms REAL)")

        now = datetime.datetime.now().isoformat()

        for msg, count in errors.items():
            c.execute(
                "INSERT INTO errors (dt, message, count) VALUES (?, ?, ?)",
                (now, msg, count)
            )

        for ep, avg_ms in api_latencies.items():
            c.execute(
                "INSERT INTO api_metrics (dt, endpoint, avg_ms) VALUES (?, ?, ?)",
                (now, ep, avg_ms)
            )
            
        conn.commit()


def generate_report(errors: Dict[str, int], api_latencies: Dict[str, float], active_sessions_count: int, output_file: str = "report.html") -> None:
    """
    Generates an HTML report summarizing system metrics.

    Args:
        errors: Dictionary of error messages and their counts.
        api_latencies: Dictionary of API endpoints and average latencies.
        active_sessions_count: Total number of active user sessions.
        output_file: Path to write the generated HTML file.
    """
    lines = [
        "<html>",
        "<head><title>System Report</title></head>",
        "<body>",
        "<h1>Error Summary</h1>",
        "<ul>"
    ]
    
    for err_msg, count in errors.items():
        lines.append(f"<li><b>{err_msg}</b>: {count} occurrences</li>")
    lines.append("</ul>")

    lines.extend([
        "<h2>API Latency</h2>",
        "<table border='1'>",
        "<tr><th>Endpoint</th><th>Avg (ms)</th></tr>"
    ])
    
    for ep, avg in api_latencies.items():
        lines.append(f"<tr><td>{ep}</td><td>{round(avg, 1)}</td></tr>")
    lines.append("</table>")

    lines.extend([
        "<h2>Active Sessions</h2>",
        f"<p>{active_sessions_count} user(s) currently active</p>",
        "</body>",
        "</html>"
    ])

    with open(output_file, "w") as f:
        f.write("\n".join(lines) + "\n")
        
    print(f"Job finished at {datetime.datetime.now()}")


def run_pipeline() -> None:
    """
    Executes the full Extract, Transform, Load (ETL) and reporting pipeline.
    """
    logs = extract_logs(LOG_FILE)
    errors, api_latencies, active_sessions_count = transform_data(logs)
    load_to_db(DB_PATH, errors, api_latencies)
    generate_report(errors, api_latencies, active_sessions_count)


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