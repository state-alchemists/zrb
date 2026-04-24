import datetime
import os
import re
import sqlite3
from typing import Dict, List, Tuple

# Config from environment variables
DB_PATH = os.getenv("DB_PATH", "metrics.db")
LOG_FILE = os.getenv("LOG_FILE", "server.log")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_USER = os.getenv("DB_USER", "admin")
DB_PASS = os.getenv("DB_PASS", "password123")

# Pre-compile regex patterns for performance
LOG_PATTERN = re.compile(r"^(?P<date>\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2})\s+(?P<level>\w+)\s+(?P<message>.*)$")
USER_PATTERN = re.compile(r"^User\s+(?P<uid>\S+)\s+(?P<action>.*)$")
API_PATTERN = re.compile(r"^API\s+(?P<endpoint>\S+)\s+took\s+(?P<ms>\d+)ms$")

def extract_logs(file_path: str) -> Tuple[List[str], List[Tuple[str, int]], Dict[str, str]]:
    """
    Extract and parse data from the log file using regex.

    Args:
        file_path: Path to the log file.

    Returns:
        A tuple containing:
        - List of error messages.
        - List of API calls as (endpoint, duration_ms) tuples.
        - Dictionary of active sessions mapping user ID to login timestamp.
    """
    errors: List[str] = []
    api_calls: List[Tuple[str, int]] = []
    sessions: Dict[str, str] = {}

    if not os.path.exists(file_path):
        return errors, api_calls, sessions

    with open(file_path, "r") as f:
        for line in f:
            match = LOG_PATTERN.match(line.strip())
            if not match:
                continue

            dt, level, message = match.group("date", "level", "message")

            if level == "ERROR":
                errors.append(message)
            elif level == "INFO":
                user_match = USER_PATTERN.match(message)
                if user_match:
                    uid, action = user_match.group("uid", "action")
                    if "logged in" in action:
                        sessions[uid] = dt
                    elif "logged out" in action and uid in sessions:
                        sessions.pop(uid)
                    continue

                api_match = API_PATTERN.match(message)
                if api_match:
                    endpoint, ms_str = api_match.group("endpoint", "ms")
                    api_calls.append((endpoint, int(ms_str)))

    return errors, api_calls, sessions

def transform_errors(errors: List[str]) -> Dict[str, int]:
    """
    Count occurrences of each error message.

    Args:
        errors: List of error messages.

    Returns:
        Dictionary mapping error message to occurrence count.
    """
    error_counts: Dict[str, int] = {}
    for err in errors:
        error_counts[err] = error_counts.get(err, 0) + 1
    return error_counts

def transform_api_metrics(api_calls: List[Tuple[str, int]]) -> Dict[str, float]:
    """
    Calculate average latency for each API endpoint.

    Args:
        api_calls: List of tuples containing (endpoint, duration_ms).

    Returns:
        Dictionary mapping endpoint to average duration in milliseconds.
    """
    stats: Dict[str, List[int]] = {}
    for endpoint, ms in api_calls:
        stats.setdefault(endpoint, []).append(ms)

    return {ep: sum(times) / len(times) for ep, times in stats.items()}

def load_to_database(db_path: str, error_counts: Dict[str, int], api_metrics: Dict[str, float]) -> None:
    """
    Save transformed metrics to the SQLite database.

    Args:
        db_path: Path to the SQLite database.
        error_counts: Dictionary of error counts.
        api_metrics: Dictionary of average API latencies.
    """
    print(f"Connecting to {DB_HOST}:{DB_PORT} as {DB_USER}...")

    with sqlite3.connect(db_path) as conn:
        c = conn.cursor()
        c.execute("CREATE TABLE IF NOT EXISTS errors (dt TEXT, message TEXT, count INTEGER)")
        c.execute("CREATE TABLE IF NOT EXISTS api_metrics (dt TEXT, endpoint TEXT, avg_ms REAL)")

        now = datetime.datetime.now().isoformat()

        for msg, count in error_counts.items():
            # SQL injection fixed with parameterized queries
            c.execute(
                "INSERT INTO errors (dt, message, count) VALUES (?, ?, ?)",
                (now, msg, count)
            )

        for ep, avg in api_metrics.items():
            # SQL injection fixed with parameterized queries
            c.execute(
                "INSERT INTO api_metrics (dt, endpoint, avg_ms) VALUES (?, ?, ?)",
                (now, ep, avg)
            )
        conn.commit()

def load_to_html(error_counts: Dict[str, int], api_metrics: Dict[str, float], active_sessions: int, output_path: str = "report.html") -> None:
    """
    Generate an HTML report with the metrics.

    Args:
        error_counts: Dictionary of error counts.
        api_metrics: Dictionary of average API latencies.
        active_sessions: Number of currently active sessions.
        output_path: Path where the HTML report will be written.
    """
    lines = [
        "<html>",
        "<head><title>System Report</title></head>",
        "<body>",
        "<h1>Error Summary</h1>",
        "<ul>"
    ]
    for err_msg, count in error_counts.items():
        lines.append(f"<li><b>{err_msg}</b>: {count} occurrences</li>")
    lines.append("</ul>")

    lines.extend([
        "<h2>API Latency</h2>",
        "<table border='1'>",
        "<tr><th>Endpoint</th><th>Avg (ms)</th></tr>"
    ])
    for ep, avg in api_metrics.items():
        lines.append(f"<tr><td>{ep}</td><td>{round(avg, 1)}</td></tr>")
    lines.append("</table>")

    lines.extend([
        "<h2>Active Sessions</h2>",
        f"<p>{active_sessions} user(s) currently active</p>",
        "</body>",
        "</html>"
    ])

    with open(output_path, "w") as f:
        f.write("\n".join(lines) + "\n")

def run_pipeline() -> None:
    """
    Main ETL pipeline execution flow.
    """
    # Extract
    errors, api_calls, sessions = extract_logs(LOG_FILE)

    # Transform
    error_counts = transform_errors(errors)
    api_metrics = transform_api_metrics(api_calls)
    active_sessions = len(sessions)

    # Load
    load_to_database(DB_PATH, error_counts, api_metrics)
    load_to_html(error_counts, api_metrics, active_sessions)

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
    run_pipeline()