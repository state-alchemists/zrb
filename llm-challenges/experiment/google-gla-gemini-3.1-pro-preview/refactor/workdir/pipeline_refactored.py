import datetime
import os
import sqlite3
import re
from typing import List, Dict, Tuple

def extract_logs(log_file: str) -> List[Dict[str, str]]:
    """
    Extracts log entries from the specified log file using regular expressions.
    
    Args:
        log_file (str): The path to the log file.
        
    Returns:
        List[Dict[str, str]]: A list of dictionaries containing timestamp, level, and message.
    """
    entries = []
    if not os.path.exists(log_file):
        return entries
        
    # Regex to capture date, time, log level, and the rest of the message
    log_pattern = re.compile(
        r"^(?P<date>\d{4}-\d{2}-\d{2})\s+(?P<time>\d{2}:\d{2}:\d{2})\s+(?P<level>[A-Z]+)\s+(?P<message>.*)$"
    )
    
    with open(log_file, "r") as f:
        for line in f:
            match = log_pattern.match(line.strip())
            if match:
                dt = f"{match.group('date')} {match.group('time')}"
                entries.append({
                    "timestamp": dt,
                    "level": match.group("level"),
                    "message": match.group("message")
                })
    return entries

def transform_data(entries: List[Dict[str, str]]) -> Tuple[Dict[str, int], Dict[str, float], int]:
    """
    Transforms log entries into aggregated metrics: error counts, API latencies, and active session counts.
    
    Args:
        entries (List[Dict[str, str]]): The parsed log entries.
        
    Returns:
        Tuple[Dict[str, int], Dict[str, float], int]: 
            - Error counts grouped by message
            - Average API latency grouped by endpoint
            - Count of currently active sessions
    """
    errors: Dict[str, int] = {}
    api_calls: Dict[str, List[int]] = {}
    sessions: Dict[str, str] = {}
    
    # Regex for specific log formats
    user_pattern = re.compile(r"^User\s+(?P<uid>\S+)\s+(?P<action>.*)$")
    api_pattern = re.compile(r"^API\s+(?P<endpoint>\S+)\s+took\s+(?P<duration>\d+)ms$")
    
    for entry in entries:
        level = entry["level"]
        message = entry["message"]
        
        if level == "ERROR":
            errors[message] = errors.get(message, 0) + 1
            
        elif level == "INFO":
            user_match = user_pattern.match(message)
            if user_match:
                uid = user_match.group("uid")
                action = user_match.group("action")
                if "logged in" in action:
                    sessions[uid] = entry["timestamp"]
                elif "logged out" in action and uid in sessions:
                    del sessions[uid]
                continue
                
            api_match = api_pattern.match(message)
            if api_match:
                endpoint = api_match.group("endpoint")
                duration = int(api_match.group("duration"))
                api_calls.setdefault(endpoint, []).append(duration)
                
    api_metrics: Dict[str, float] = {}
    for ep, times in api_calls.items():
        api_metrics[ep] = sum(times) / len(times)
        
    return errors, api_metrics, len(sessions)

def load_data(db_path: str, errors: Dict[str, int], api_metrics: Dict[str, float]) -> None:
    """
    Loads the aggregated metrics into the SQLite database safely using parameterized queries.
    
    Args:
        db_path (str): The path to the SQLite database.
        errors (Dict[str, int]): Error counts to store.
        api_metrics (Dict[str, float]): Average API latencies to store.
    """
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS errors (dt TEXT, message TEXT, count INTEGER)")
    c.execute("CREATE TABLE IF NOT EXISTS api_metrics (dt TEXT, endpoint TEXT, avg_ms REAL)")
    
    now = str(datetime.datetime.now())
    
    for msg, count in errors.items():
        c.execute(
            "INSERT INTO errors (dt, message, count) VALUES (?, ?, ?)",
            (now, msg, count)
        )
        
    for ep, avg in api_metrics.items():
        c.execute(
            "INSERT INTO api_metrics (dt, endpoint, avg_ms) VALUES (?, ?, ?)",
            (now, ep, avg)
        )
        
    conn.commit()
    conn.close()

def generate_report(errors: Dict[str, int], api_metrics: Dict[str, float], active_sessions: int, report_file: str) -> None:
    """
    Generates an HTML report summarizing the system metrics.
    
    Args:
        errors (Dict[str, int]): Error counts.
        api_metrics (Dict[str, float]): Average API latencies.
        active_sessions (int): Number of currently active sessions.
        report_file (str): The output path for the HTML report.
    """
    out = "<html>\n<head><title>System Report</title></head>\n<body>\n"
    out += "<h1>Error Summary</h1>\n<ul>\n"
    for err_msg, count in errors.items():
        out += f"<li><b>{err_msg}</b>: {count} occurrences</li>\n"
    out += "</ul>\n"

    out += "<h2>API Latency</h2>\n<table border='1'>\n"
    out += "<tr><th>Endpoint</th><th>Avg (ms)</th></tr>\n"
    for ep, avg in api_metrics.items():
        out += f"<tr><td>{ep}</td><td>{round(avg, 1)}</td></tr>\n"
    out += "</table>\n"

    out += "<h2>Active Sessions</h2>\n"
    out += f"<p>{active_sessions} user(s) currently active</p>\n"
    out += "</body>\n</html>"

    with open(report_file, "w") as f:
        f.write(out)

def process_pipeline() -> None:
    """
    Main execution function orchestrating Extract, Transform, Load (ETL), and reporting.
    """
    # Use environment variables for configuration
    db_path = os.getenv("DB_PATH", "metrics.db")
    log_file = os.getenv("LOG_FILE", "server.log")
    db_host = os.getenv("DB_HOST", "localhost")
    db_port = os.getenv("DB_PORT", "5432")
    db_user = os.getenv("DB_USER", "admin")
    
    print(f"Connecting to {db_host}:{db_port} as {db_user}...")
    
    # ETL Process
    entries = extract_logs(log_file)
    errors, api_metrics, active_sessions = transform_data(entries)
    load_data(db_path, errors, api_metrics)
    
    # Reporting
    generate_report(errors, api_metrics, active_sessions, report_file="report.html")
    
    print(f"Job finished at {datetime.datetime.now()}")

if __name__ == "__main__":
    # For testing purposes, generate a dummy log file if it doesn't exist
    log_file_path = os.getenv("LOG_FILE", "server.log")
    if not os.path.exists(log_file_path):
        with open(log_file_path, "w") as f:
            f.write("2024-01-01 12:00:00 INFO User 42 logged in\n")
            f.write("2024-01-01 12:05:00 ERROR Database timeout\n")
            f.write("2024-01-01 12:05:05 ERROR Database timeout\n")
            f.write("2024-01-01 12:08:00 INFO API /users/profile took 250ms\n")
            f.write("2024-01-01 12:09:00 WARN Memory usage at 87%\n")
            f.write("2024-01-01 12:10:00 INFO User 42 logged out\n")
            
    process_pipeline()
