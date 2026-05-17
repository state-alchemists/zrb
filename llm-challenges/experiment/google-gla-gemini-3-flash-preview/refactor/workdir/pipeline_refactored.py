import datetime
import os
import re
import sqlite3
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass

# Configuration from environment variables
DB_PATH = os.environ.get("DB_PATH", "metrics.db")
LOG_FILE = os.environ.get("LOG_FILE", "server.log")
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = os.environ.get("DB_PORT", "5432")
DB_USER = os.environ.get("DB_USER", "admin")
DB_PASS = os.environ.get("DB_PASS", "password123")

@dataclass
class LogEntry:
    timestamp: str
    level: str
    message: str

@dataclass
class ApiCall:
    timestamp: str
    endpoint: str
    duration_ms: int

@dataclass
class UserAction:
    timestamp: str
    user_id: str
    action: str

def load_config() -> Dict[str, str]:
    """Load configuration from environment variables."""
    return {
        "db_path": DB_PATH,
        "log_file": LOG_FILE,
        "db_host": DB_HOST,
        "db_port": DB_PORT,
        "db_user": DB_USER,
    }

def parse_logs(file_path: str) -> Tuple[List[LogEntry], List[ApiCall], List[UserAction]]:
    """
    Extract: Read log file and parse lines using regex.
    Returns a tuple of (errors/warnings, api_calls, user_actions).
    """
    entries = []
    api_calls = []
    user_actions = []

    # Regex for standard log format: YYYY-MM-DD HH:MM:SS LEVEL Message
    log_pattern = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s+(\w+)\s+(.*)$")
    # Specific patterns for User and API info
    user_pattern = re.compile(r"User\s+(\w+)\s+(.*)")
    api_pattern = re.compile(r"API\s+(\S+)\s+took\s+(\d+)ms")

    if not os.path.exists(file_path):
        return entries, api_calls, user_actions

    with open(file_path, "r") as f:
        for line in f:
            line = line.strip()
            match = log_pattern.match(line)
            if not match:
                continue

            dt, lvl, msg = match.groups()

            if lvl in ("ERROR", "WARN"):
                entries.append(LogEntry(dt, lvl, msg))
            
            if "User" in msg:
                u_match = user_pattern.search(msg)
                if u_match:
                    uid, action = u_match.groups()
                    user_actions.append(UserAction(dt, uid, action))
            
            if "API" in msg:
                a_match = api_pattern.search(msg)
                if a_match:
                    endpoint, dur = a_match.groups()
                    api_calls.append(ApiCall(dt, endpoint, int(dur)))

    return entries, api_calls, user_actions

def transform_metrics(
    entries: List[LogEntry], api_calls: List[ApiCall], user_actions: List[UserAction]
) -> Dict[str, Any]:
    """
    Transform: Process raw entries into summarized metrics.
    """
    # Error summary
    error_counts = {}
    for entry in entries:
        if entry.level == "ERROR":
            error_counts[entry.message] = error_counts.get(entry.message, 0) + 1

    # API Latency stats
    endpoint_durations = {}
    for call in api_calls:
        endpoint_durations.setdefault(call.endpoint, []).append(call.duration_ms)
    
    api_metrics = {
        ep: sum(durs) / len(durs) for ep, durs in endpoint_durations.items()
    }

    # Active sessions
    sessions = {}
    for ua in user_actions:
        if "logged in" in ua.action:
            sessions[ua.user_id] = ua.timestamp
        elif "logged out" in ua.action and ua.user_id in sessions:
            sessions.pop(ua.user_id)

    return {
        "error_counts": error_counts,
        "api_metrics": api_metrics,
        "active_session_count": len(sessions)
    }

def load_to_db(db_path: str, metrics: Dict[str, Any]) -> None:
    """
    Load: Store metrics in database using parameterized queries.
    """
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = sqlite3.connect(db_path)
    try:
        c = conn.cursor()
        c.execute("CREATE TABLE IF NOT EXISTS errors (dt TEXT, message TEXT, count INTEGER)")
        c.execute("CREATE TABLE IF NOT EXISTS api_metrics (dt TEXT, endpoint TEXT, avg_ms REAL)")

        # Parameterized queries to prevent SQL injection
        for msg, count in metrics["error_counts"].items():
            c.execute(
                "INSERT INTO errors (dt, message, count) VALUES (?, ?, ?)",
                (now, msg, count)
            )

        for ep, avg in metrics["api_metrics"].items():
            c.execute(
                "INSERT INTO api_metrics (dt, endpoint, avg_ms) VALUES (?, ?, ?)",
                (now, ep, avg)
            )

        conn.commit()
    finally:
        conn.close()

def generate_report(metrics: Dict[str, Any], output_path: str = "report.html") -> None:
    """
    Generate the HTML report.
    """
    html_content = [
        "<html>",
        "<head><title>System Report</title></head>",
        "<body>",
        "<h1>Error Summary</h1>",
        "<ul>"
    ]
    
    for err_msg, count in metrics["error_counts"].items():
        html_content.append(f"<li><b>{err_msg}</b>: {count} occurrences</li>")
    
    html_content.extend([
        "</ul>",
        "<h2>API Latency</h2>",
        "<table border='1'>",
        "<tr><th>Endpoint</th><th>Avg (ms)</th></tr>"
    ])
    
    for ep, avg in metrics["api_metrics"].items():
        html_content.append(f"<tr><td>{ep}</td><td>{round(avg, 1)}</td></tr>")
    
    html_content.extend([
        "</table>",
        "<h2>Active Sessions</h2>",
        f"<p>{metrics['active_session_count']} user(s) currently active</p>",
        "</body>",
        "</html>"
    ])

    with open(output_path, "w") as f:
        f.write("\n".join(html_content))

def main() -> None:
    """Main pipeline execution."""
    config = load_config()
    print(f"Connecting to {config['db_host']}:{config['db_port']} as {config['db_user']}...")

    # ETL Pipeline
    log_entries, api_calls, user_actions = parse_logs(config["log_file"])
    metrics = transform_metrics(log_entries, api_calls, user_actions)
    load_to_db(config["db_path"], metrics)
    generate_report(metrics)

    print(f"Job finished at {datetime.datetime.now()}")

if __name__ == "__main__":
    main()
