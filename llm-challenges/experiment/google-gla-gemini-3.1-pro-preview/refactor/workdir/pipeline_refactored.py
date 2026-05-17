import datetime
import os
import re
import sqlite3
from typing import Any, Dict, List, Tuple

# Load config from environment variables with fallbacks
DB_PATH = os.getenv("DB_PATH", "metrics.db")
LOG_FILE = os.getenv("LOG_FILE", "server.log")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_USER = os.getenv("DB_USER", "admin")
DB_PASS = os.getenv("DB_PASS", "password123")

# Regex pattern for basic log line: YYYY-MM-DD HH:MM:SS LEVEL Message
LOG_PATTERN = re.compile(r"^(?P<dt>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s+(?P<level>[A-Z]+)\s+(?P<message>.*)$")
USER_PATTERN = re.compile(r"^User (?P<uid>\S+) (?P<action>.*)$")
API_PATTERN = re.compile(r"^API (?P<endpoint>\S+) took (?P<ms>\d+)ms$")


def extract_logs(log_file: str) -> List[Dict[str, Any]]:
    """
    Reads and parses a log file using regex.

    Args:
        log_file (str): The path to the log file.

    Returns:
        List[Dict[str, Any]]: A list of parsed log events.
    """
    events = []
    if not os.path.exists(log_file):
        return events

    with open(log_file, "r", encoding="utf-8") as f:
        for line in f:
            match = LOG_PATTERN.match(line.strip())
            if not match:
                continue

            dt = match.group("dt")
            level = match.group("level")
            message = match.group("message")

            event: Dict[str, Any] = {"dt": dt, "level": level, "message": message}

            if level == "INFO":
                user_match = USER_PATTERN.match(message)
                if user_match:
                    event["type"] = "user"
                    event["uid"] = user_match.group("uid")
                    event["action"] = user_match.group("action")
                else:
                    api_match = API_PATTERN.match(message)
                    if api_match:
                        event["type"] = "api"
                        event["endpoint"] = api_match.group("endpoint")
                        event["ms"] = int(api_match.group("ms"))

            events.append(event)

    return events


def transform_data(events: List[Dict[str, Any]]) -> Tuple[Dict[str, int], Dict[str, float], int]:
    """
    Transforms raw parsed logs into aggregated metrics.

    Args:
        events (List[Dict[str, Any]]): Parsed log events.

    Returns:
        Tuple[Dict[str, int], Dict[str, float], int]:
            - A dictionary mapping error messages to their occurrence count.
            - A dictionary mapping API endpoints to their average latency in ms.
            - The number of currently active sessions.
    """
    errors: Dict[str, int] = {}
    endpoint_times: Dict[str, List[int]] = {}
    active_users = set()

    for event in events:
        if event["level"] == "ERROR":
            msg = event["message"]
            errors[msg] = errors.get(msg, 0) + 1

        elif event.get("type") == "user":
            uid = event["uid"]
            action = event["action"]
            if "logged in" in action:
                active_users.add(uid)
            elif "logged out" in action:
                active_users.discard(uid)

        elif event.get("type") == "api":
            ep = event["endpoint"]
            ms = event["ms"]
            endpoint_times.setdefault(ep, []).append(ms)

    api_metrics: Dict[str, float] = {}
    for ep, times in endpoint_times.items():
        if times:
            api_metrics[ep] = sum(times) / len(times)

    return errors, api_metrics, len(active_users)


def load_to_db(db_path: str, errors: Dict[str, int], api_metrics: Dict[str, float]) -> None:
    """
    Loads aggregated error and API metrics into the SQLite database.

    Args:
        db_path (str): The path to the SQLite database.
        errors (Dict[str, int]): Aggregated error counts.
        api_metrics (Dict[str, float]): Aggregated average API latencies.
    """
    print(f"Connecting to {DB_HOST}:{DB_PORT} as {DB_USER}...")

    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS errors (dt TEXT, message TEXT, count INTEGER)")
    c.execute("CREATE TABLE IF NOT EXISTS api_metrics (dt TEXT, endpoint TEXT, avg_ms REAL)")

    now_str = str(datetime.datetime.now())

    # Use parameterized queries to prevent SQL injection
    error_rows = [(now_str, msg, count) for msg, count in errors.items()]
    c.executemany("INSERT INTO errors VALUES (?, ?, ?)", error_rows)

    api_rows = [(now_str, ep, avg) for ep, avg in api_metrics.items()]
    c.executemany("INSERT INTO api_metrics VALUES (?, ?, ?)", api_rows)

    conn.commit()
    conn.close()


def generate_report(errors: Dict[str, int], api_metrics: Dict[str, float], active_sessions: int, output_file: str = "report.html") -> None:
    """
    Generates an HTML report containing the aggregated metrics.

    Args:
        errors (Dict[str, int]): Aggregated error counts.
        api_metrics (Dict[str, float]): Aggregated average API latencies.
        active_sessions (int): The number of active user sessions.
        output_file (str): The file path to write the report to.
    """
    html = ["<html>", "<head><title>System Report</title></head>", "<body>"]

    html.append("<h1>Error Summary</h1>")
    html.append("<ul>")
    for err_msg, count in errors.items():
        html.append(f"<li><b>{err_msg}</b>: {count} occurrences</li>")
    html.append("</ul>")

    html.append("<h2>API Latency</h2>")
    html.append("<table border='1'>")
    html.append("<tr><th>Endpoint</th><th>Avg (ms)</th></tr>")
    for ep, avg in api_metrics.items():
        html.append(f"<tr><td>{ep}</td><td>{round(avg, 1)}</td></tr>")
    html.append("</table>")

    html.append("<h2>Active Sessions</h2>")
    html.append(f"<p>{active_sessions} user(s) currently active</p>")
    html.append("</body>")
    html.append("</html>\n")

    with open(output_file, "w", encoding="utf-8") as f:
        f.write("\n".join(html))


def main() -> None:
    """
    Main entry point for the ETL pipeline.
    """
    events = extract_logs(LOG_FILE)
    errors, api_metrics, active_sessions = transform_data(events)
    load_to_db(DB_PATH, errors, api_metrics)
    generate_report(errors, api_metrics, active_sessions)
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
    main()
