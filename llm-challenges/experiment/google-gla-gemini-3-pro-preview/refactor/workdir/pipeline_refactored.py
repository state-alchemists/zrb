import datetime
import os
import re
import sqlite3
from dataclasses import dataclass
from typing import Any, Dict, List, Set, Tuple

@dataclass
class Config:
    """Configuration settings loaded from environment variables."""
    db_path: str
    log_file: str
    db_host: str
    db_port: int
    db_user: str
    db_pass: str

# Regex patterns for log parsing
LOG_PATTERN = re.compile(r"^(?P<timestamp>\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2})\s+(?P<level>\w+)\s+(?P<message>.*)$")
USER_PATTERN = re.compile(r"^User\s+(?P<uid>\S+)\s+(?P<action>.*)$")
API_PATTERN = re.compile(r"^API\s+(?P<endpoint>\S+)\s+took\s+(?P<duration>\d+)ms$")

def get_config() -> Config:
    """Loads configuration from environment variables with defaults."""
    return Config(
        db_path=os.getenv("DB_PATH", "metrics.db"),
        log_file=os.getenv("LOG_FILE", "server.log"),
        db_host=os.getenv("DB_HOST", "localhost"),
        db_port=int(os.getenv("DB_PORT", "5432")),
        db_user=os.getenv("DB_USER", "admin"),
        db_pass=os.getenv("DB_PASS", "password123")
    )

def extract_logs(log_file: str) -> List[Dict[str, Any]]:
    """
    Reads and parses the log file into a list of structured event dictionaries.
    
    Args:
        log_file: Path to the log file.
        
    Returns:
        List of dictionaries containing parsed event data.
    """
    events: List[Dict[str, Any]] = []
    if not os.path.exists(log_file):
        return events

    with open(log_file, "r") as f:
        for line in f:
            match = LOG_PATTERN.match(line.strip())
            if not match:
                continue

            level = match.group("level")
            message = match.group("message")
            timestamp = match.group("timestamp")

            if level == "ERROR":
                events.append({"type": "error", "message": message.strip(), "timestamp": timestamp})
            elif level == "INFO":
                user_match = USER_PATTERN.match(message)
                if user_match:
                    events.append({
                        "type": "user_action",
                        "uid": user_match.group("uid"),
                        "action": user_match.group("action").strip(),
                        "timestamp": timestamp
                    })
                    continue

                api_match = API_PATTERN.match(message)
                if api_match:
                    events.append({
                        "type": "api_call",
                        "endpoint": api_match.group("endpoint"),
                        "duration_ms": int(api_match.group("duration")),
                        "timestamp": timestamp
                    })
                    continue
    return events

def transform_logs(events: List[Dict[str, Any]]) -> Tuple[Dict[str, int], Dict[str, float], int]:
    """
    Aggregates log events into computed metrics.
    
    Args:
        events: List of structured log event dictionaries.
        
    Returns:
        Tuple containing error counts, average API latencies, and active sessions count.
    """
    error_counts: Dict[str, int] = {}
    api_latencies: Dict[str, List[int]] = {}
    active_sessions: Set[str] = set()

    for event in events:
        if event["type"] == "error":
            msg = event["message"]
            error_counts[msg] = error_counts.get(msg, 0) + 1
        elif event["type"] == "api_call":
            ep = event["endpoint"]
            api_latencies.setdefault(ep, []).append(event["duration_ms"])
        elif event["type"] == "user_action":
            uid = event["uid"]
            action = event["action"]
            if "logged in" in action:
                active_sessions.add(uid)
            elif "logged out" in action:
                active_sessions.discard(uid)

    api_metrics = {
        ep: sum(times) / len(times) for ep, times in api_latencies.items()
    }

    return error_counts, api_metrics, len(active_sessions)

def load_to_database(db_path: str, error_counts: Dict[str, int], api_metrics: Dict[str, float]) -> None:
    """
    Saves aggregated metrics to the SQLite database securely.
    
    Args:
        db_path: Path to the SQLite database file.
        error_counts: Dictionary of error messages and their occurrence counts.
        api_metrics: Dictionary of API endpoints and their average latencies.
    """
    now = str(datetime.datetime.now())
    with sqlite3.connect(db_path) as conn:
        c = conn.cursor()
        c.execute("CREATE TABLE IF NOT EXISTS errors (dt TEXT, message TEXT, count INTEGER)")
        c.execute("CREATE TABLE IF NOT EXISTS api_metrics (dt TEXT, endpoint TEXT, avg_ms REAL)")

        for msg, count in error_counts.items():
            c.execute(
                "INSERT INTO errors (dt, message, count) VALUES (?, ?, ?)",
                (now, msg, count)
            )

        for ep, avg_ms in api_metrics.items():
            c.execute(
                "INSERT INTO api_metrics (dt, endpoint, avg_ms) VALUES (?, ?, ?)",
                (now, ep, avg_ms)
            )
        conn.commit()

def generate_html_report(error_counts: Dict[str, int], api_metrics: Dict[str, float], active_sessions_count: int, output_file: str = "report.html") -> None:
    """
    Generates an HTML report summarizing system status and metrics.
    
    Args:
        error_counts: Dictionary of error messages and their occurrence counts.
        api_metrics: Dictionary of API endpoints and their average latencies.
        active_sessions_count: Number of currently active user sessions.
        output_file: Path to write the output HTML report.
    """
    out = "<html>\n<head><title>System Report</title></head>\n<body>\n"
    out += "<h1>Error Summary</h1>\n<ul>\n"
    for err_msg, count in error_counts.items():
        out += f"<li><b>{err_msg}</b>: {count} occurrences</li>\n"
    out += "</ul>\n"

    out += "<h2>API Latency</h2>\n<table border='1'>\n"
    out += "<tr><th>Endpoint</th><th>Avg (ms)</th></tr>\n"
    for ep, avg in api_metrics.items():
        out += f"<tr><td>{ep}</td><td>{round(avg, 1)}</td></tr>\n"
    out += "</table>\n"

    out += "<h2>Active Sessions</h2>\n"
    out += f"<p>{active_sessions_count} user(s) currently active</p>\n"
    out += "</body>\n</html>"

    with open(output_file, "w") as f:
        f.write(out)

def main() -> None:
    """Main execution block combining extraction, transformation, and loading."""
    config = get_config()

    print(f"Connecting to {config.db_host}:{config.db_port} as {config.db_user}...")

    # Extract
    events = extract_logs(config.log_file)

    # Transform
    error_counts, api_metrics, active_sessions = transform_logs(events)

    # Load
    load_to_database(config.db_path, error_counts, api_metrics)
    generate_html_report(error_counts, api_metrics, active_sessions)

    print(f"Job finished at {datetime.datetime.now()}")

if __name__ == "__main__":
    config = get_config()
    if not os.path.exists(config.log_file):
        with open(config.log_file, "w") as f:
            f.write("2024-01-01 12:00:00 INFO User 42 logged in\n")
            f.write("2024-01-01 12:05:00 ERROR Database timeout\n")
            f.write("2024-01-01 12:05:05 ERROR Database timeout\n")
            f.write("2024-01-01 12:08:00 INFO API /users/profile took 250ms\n")
            f.write("2024-01-01 12:09:00 WARN Memory usage at 87%\n")
            f.write("2024-01-01 12:10:00 INFO User 42 logged out\n")
    main()
