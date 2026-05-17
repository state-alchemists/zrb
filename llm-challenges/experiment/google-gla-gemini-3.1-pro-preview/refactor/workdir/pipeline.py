import datetime
import os
import re
import sqlite3
from typing import Dict, Iterable, List, Set, Tuple

# --- Configuration ---
# Loaded from environment variables with defaults for local development
DB_PATH = os.getenv("DB_PATH", "metrics.db")
LOG_FILE = os.getenv("LOG_FILE", "server.log")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_USER = os.getenv("DB_USER", "admin")
DB_PASS = os.getenv("DB_PASS", "password123")

# --- Compiled Regex Patterns ---
LOG_PATTERN = re.compile(r"^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s+(?P<level>[A-Z]+)\s+(?P<message>.*)$")
USER_PATTERN = re.compile(r"^User (?P<uid>\S+)\s+(?P<action>.*)$")
API_PATTERN = re.compile(r"^API (?P<endpoint>\S+)\s+took\s+(?P<ms>\d+)ms$")


def extract_logs(file_path: str) -> Iterable[str]:
    """
    Reads and yields log lines from the given file path.
    
    Args:
        file_path: Path to the log file.
        
    Yields:
        Stripped lines from the log file.
    """
    if not os.path.exists(file_path):
        return
        
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            yield line.strip()


def transform_logs(lines: Iterable[str]) -> Tuple[Dict[str, int], Dict[str, float], int]:
    """
    Parses log lines to aggregate error counts, API latency, and active sessions.
    
    Args:
        lines: An iterable of log line strings.
        
    Returns:
        A tuple containing:
            - Dict mapping error messages to their occurrence count.
            - Dict mapping API endpoints to their average latency in ms.
            - Integer representing the count of currently active sessions.
    """
    error_counts: Dict[str, int] = {}
    api_calls: Dict[str, List[int]] = {}
    active_sessions: Set[str] = set()

    for line in lines:
        match = LOG_PATTERN.match(line)
        if not match:
            continue
        
        level = match.group("level")
        message = match.group("message")
        
        if level == "ERROR":
            error_counts[message] = error_counts.get(message, 0) + 1
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
                ms = int(api_match.group("ms"))
                api_calls.setdefault(endpoint, []).append(ms)

    # Calculate average API latency
    api_avg_latencies = {
        ep: sum(times) / len(times) 
        for ep, times in api_calls.items() 
        if times
    }

    return error_counts, api_avg_latencies, len(active_sessions)


def load_metrics_to_db(db_path: str, error_counts: Dict[str, int], api_avg_latencies: Dict[str, float]) -> None:
    """
    Saves aggregated error and API metrics to the SQLite database.
    
    Args:
        db_path: Path to the SQLite database file.
        error_counts: Dict of error messages and their counts.
        api_avg_latencies: Dict of API endpoints and their average latency.
    """
    print(f"Connecting to {DB_HOST}:{DB_PORT} as {DB_USER}...")
    
    with sqlite3.connect(db_path) as conn:
        c = conn.cursor()
        c.execute("CREATE TABLE IF NOT EXISTS errors (dt TEXT, message TEXT, count INTEGER)")
        c.execute("CREATE TABLE IF NOT EXISTS api_metrics (dt TEXT, endpoint TEXT, avg_ms REAL)")
        
        now_str = str(datetime.datetime.now())
        
        # Parameterized queries prevent SQL injection
        error_records = [(now_str, msg, count) for msg, count in error_counts.items()]
        c.executemany("INSERT INTO errors (dt, message, count) VALUES (?, ?, ?)", error_records)
        
        api_records = [(now_str, ep, avg) for ep, avg in api_avg_latencies.items()]
        c.executemany("INSERT INTO api_metrics (dt, endpoint, avg_ms) VALUES (?, ?, ?)", api_records)
        
        conn.commit()


def generate_html_report(error_counts: Dict[str, int], api_avg_latencies: Dict[str, float], active_sessions: int, output_path: str = "report.html") -> None:
    """
    Generates an HTML report summarizing the system metrics.
    
    Args:
        error_counts: Dict mapping error messages to occurrence counts.
        api_avg_latencies: Dict mapping API endpoints to average latency.
        active_sessions: The count of active user sessions.
        output_path: File path to save the HTML report.
    """
    html = (
        "<html>\n"
        "<head><title>System Report</title></head>\n"
        "<body>\n"
        "<h1>Error Summary</h1>\n"
        "<ul>\n"
    )
    for err_msg, count in error_counts.items():
        html += f"<li><b>{err_msg}</b>: {count} occurrences</li>\n"
    html += "</ul>\n"
    
    html += "<h2>API Latency</h2>\n<table border='1'>\n"
    html += "<tr><th>Endpoint</th><th>Avg (ms)</th></tr>\n"
    for ep, avg in api_avg_latencies.items():
        html += f"<tr><td>{ep}</td><td>{round(avg, 1)}</td></tr>\n"
    html += "</table>\n"
    
    html += "<h2>Active Sessions</h2>\n"
    html += f"<p>{active_sessions} user(s) currently active</p>\n"
    html += "</body>\n</html>"
    
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)


def run_pipeline() -> None:
    """
    Orchestrates the Extract-Transform-Load (ETL) pipeline and reporting.
    """
    lines = extract_logs(LOG_FILE)
    error_counts, api_avg_latencies, active_sessions = transform_logs(lines)
    
    load_metrics_to_db(DB_PATH, error_counts, api_avg_latencies)
    generate_html_report(error_counts, api_avg_latencies, active_sessions)
    
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
