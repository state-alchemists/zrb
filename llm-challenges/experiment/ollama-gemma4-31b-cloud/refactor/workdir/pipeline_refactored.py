import os
import re
import sqlite3
import datetime
from dataclasses import dataclass
from typing import List, Dict, Any, Tuple, Optional

@dataclass
class Config:
    """Application configuration loaded from environment variables."""
    db_path: str = os.getenv("DB_PATH", "metrics.db")
    log_file: str = os.getenv("LOG_FILE", "server.log")
    db_host: str = os.getenv("DB_HOST", "localhost")
    db_port: int = int(os.getenv("DB_PORT", "5432"))
    db_user: str = os.getenv("DB_USER", "admin")
    db_pass: str = os.getenv("DB_PASS", "password123")

# --- Extract ---

def parse_logs(file_path: str) -> Tuple[List[Dict[str, Any]], Dict[str, str], List[Dict[str, Any]]]:
    """
    Parses the server log file using regex.
    
    Returns:
        - errors: List of error occurrences.
        - active_sessions: Current map of active user sessions.
        - api_calls: List of API call metrics.
    """
    errors = []
    active_sessions = {}
    api_calls = []

    # Regex patterns for different log levels
    # Expected log format: YYYY-MM-DD HH:MM:SS LEVEL Message...
    log_pattern = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) (\w+) (.+)$")
    user_pattern = re.compile(r"User (\S+) (logged in|logged out)")
    api_pattern = re.compile(r"API (\S+) took (\d+)ms")

    if not os.path.exists(file_path):
        return errors, active_sessions, api_calls

    with open(file_path, "r") as f:
        for line in f:
            line = line.strip()
            match = log_pattern.match(line)
            if not match:
                continue

            timestamp, level, message = match.groups()

            if level == "ERROR":
                errors.append({"timestamp": timestamp, "message": message})
            
            elif level == "INFO":
                # Check for user session events
                user_match = user_pattern.search(message)
                if user_match:
                    uid, action = user_match.groups()
                    if action == "logged in":
                        active_sessions[uid] = timestamp
                    elif action == "logged out":
                        active_sessions.pop(uid, None)
                
                # Check for API calls
                api_match = api_pattern.search(message)
                if api_match:
                    endpoint, duration = api_match.groups()
                    api_calls.append({"timestamp": timestamp, "endpoint": endpoint, "duration": int(duration)})
            
            elif level == "WARN":
                # Warnings are parsed but not explicitly used in the final report requirements 
                # other than being present in the log. Keeping for completeness.
                pass

    return errors, active_sessions, api_calls

# --- Transform ---

def aggregate_metrics(errors: List[Dict[str, Any]], api_calls: List[Dict[str, Any]]) -> Tuple[Dict[str, int], Dict[str, float]]:
    """
    Processes raw log data into summarized metrics.
    
    Returns:
        - error_counts: Map of error message to occurrence count.
        - api_avg_latencies: Map of endpoint to average latency.
    """
    error_counts = {}
    for err in errors:
        msg = err["message"]
        error_counts[msg] = error_counts.get(msg, 0) + 1

    endpoint_times = {}
    for call in api_calls:
        ep = call["endpoint"]
        endpoint_times.setdefault(ep, []).append(call["duration"])

    api_avg_latencies = {ep: sum(times) / len(times) for ep, times in endpoint_times.items()}
    
    return error_counts, api_avg_latencies

# --- Load ---

def save_metrics_to_db(config: Config, error_summary: Dict[str, int], api_summary: Dict[str, float]) -> None:
    """
    Saves aggregated metrics to the SQLite database using parameterized queries.
    """
    print(f"Connecting to {config.db_host}:{config.db_port} as {config.db_user}...")
    
    with sqlite3.connect(config.db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE IF NOT EXISTS errors (dt TEXT, message TEXT, count INTEGER)")
        cursor.execute("CREATE TABLE IF NOT EXISTS api_metrics (dt TEXT, endpoint TEXT, avg_ms REAL)")

        now = datetime.datetime.now().isoformat()

        for msg, count in error_summary.items():
            cursor.execute("INSERT INTO errors VALUES (?, ?, ?)", (now, msg, count))

        for ep, avg in api_summary.items():
            cursor.execute("INSERT INTO api_metrics VALUES (?, ?, ?)", (now, ep, avg))
        
        conn.commit()

def generate_html_report(output_path: str, error_summary: Dict[str, int], api_summary: Dict[str, float], active_sessions_count: int) -> None:
    """Generates the final HTML report."""
    html = "<html>\n<head><title>System Report</title></head>\n<body>\n"
    html += "<h1>Error Summary</h1>\n<ul>\n"
    for msg, count in error_summary.items():
        html += f"<li><b>{msg}</b>: {count} occurrences</li>\n"
    html += "</ul>\n"

    html += "<h2>API Latency</h2>\n<table border='1'>\n"
    html += "<tr><th>Endpoint</th><th>Avg (ms)</th></tr>\n"
    for ep, avg in api_summary.items():
        html += f"<tr><td>{ep}</td><td>{round(avg, 1)}</td></tr>\n"
    html += "</table>\n"

    html += f"<h2>Active Sessions</h2>\n<p>{active_sessions_count} user(s) currently active</p>\n"
    html += "</body>\n</html>"

    with open(output_path, "w") as f:
        f.write(html)

# --- Pipeline ---

def run_pipeline():
    """Main execution pipeline."""
    config = Config()
    
    # Extract
    errors, sessions, api_calls = parse_logs(config.log_file)
    
    # Transform
    error_summary, api_summary = aggregate_metrics(errors, api_calls)
    
    # Load (DB)
    save_metrics_to_db(config, error_summary, api_summary)
    
    # Load (Report)
    generate_html_report("report.html", error_summary, api_summary, len(sessions))

    print(f"Job finished at {datetime.datetime.now()}")

if __name__ == "__main__":
    # Mirroring the original's sample-file creation for testability
    default_config = Config()
    if not os.path.exists(default_config.log_file):
        with open(default_config.log_file, "w") as f:
            f.write("2024-01-01 12:00:00 INFO User 42 logged in\n")
            f.write("2024-01-01 12:05:00 ERROR Database timeout\n")
            f.write("2024-01-01 12:05:05 ERROR Database timeout\n")
            f.write("2024-01-01 12:08:00 INFO API /users/profile took 250ms\n")
            f.write("2024-01-01 12:09:00 WARN Memory usage at 87%\n")
            f.write("2024-01-01 12:10:00 INFO User 42 logged out\n")
    
    run_pipeline()
