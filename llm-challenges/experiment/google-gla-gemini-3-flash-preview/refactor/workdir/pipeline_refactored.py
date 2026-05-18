import datetime
import os
import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Configuration from environment variables with defaults
DB_PATH = Path(os.getenv("DB_PATH", "metrics.db"))
LOG_FILE = Path(os.getenv("LOG_FILE", "server.log"))
# Note: DB_HOST, DB_PORT, DB_USER, DB_PASS are defined in the original but not used for SQLite.
# They are kept here for environment variable requirement compliance.
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_USER = os.getenv("DB_USER", "admin")
DB_PASS = os.getenv("DB_PASS", "password123")

# Regex patterns for log parsing
LOG_PATTERN = re.compile(r"^(?P<dt>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) (?P<lvl>INFO|ERROR|WARN) (?P<msg>.*)$")
USER_ACTION_PATTERN = re.compile(r"^User (?P<uid>\S+) (?P<action>.*)$")
API_LATENCY_PATTERN = re.compile(r"^API (?P<endpoint>\S+) took (?P<ms>\d+)ms$")

@dataclass(frozen=True, slots=True)
class LogEntry:
    """Represents a single parsed log line."""
    dt: str
    lvl: str
    msg: str

@dataclass
class ProcessedMetrics:
    """Aggregated metrics from logs."""
    error_counts: Dict[str, int] = field(default_factory=dict)
    api_latencies: Dict[str, List[int]] = field(default_factory=dict)
    active_sessions: Dict[str, str] = field(default_factory=dict)

def extract(log_path: Path) -> List[LogEntry]:
    """
    Reads the log file and parses lines into LogEntry objects.
    
    :param log_path: Path to the log file.
    :return: List of LogEntry objects.
    """
    entries = []
    if not log_path.exists():
        return entries

    with log_path.open("r") as f:
        for line in f:
            match = LOG_PATTERN.match(line.strip())
            if match:
                entries.append(LogEntry(**match.groupdict()))
    return entries

def transform(entries: List[LogEntry]) -> ProcessedMetrics:
    """
    Aggregates metrics from log entries.
    
    :param entries: List of LogEntry objects.
    :return: ProcessedMetrics object containing aggregated data.
    """
    metrics = ProcessedMetrics()
    
    for entry in entries:
        if entry.lvl == "ERROR":
            metrics.error_counts[entry.msg] = metrics.error_counts.get(entry.msg, 0) + 1
        
        elif entry.lvl == "INFO":
            # Check for API latency
            api_match = API_LATENCY_PATTERN.match(entry.msg)
            if api_match:
                endpoint = api_match.group("endpoint")
                ms = int(api_match.group("ms"))
                metrics.api_latencies.setdefault(endpoint, []).append(ms)
                continue
            
            # Check for User actions
            user_match = USER_ACTION_PATTERN.match(entry.msg)
            if user_match:
                uid = user_match.group("uid")
                action = user_match.group("action")
                if "logged in" in action:
                    metrics.active_sessions[uid] = entry.dt
                elif "logged out" in action and uid in metrics.active_sessions:
                    metrics.active_sessions.pop(uid)

    return metrics

def load(metrics: ProcessedMetrics, db_path: Path, report_path: str = "report.html") -> None:
    """
    Saves metrics to the database and generates an HTML report.
    
    :param metrics: Aggregated metrics to save and report.
    :param db_path: Path to the SQLite database.
    :param report_path: Path to the output HTML report.
    """
    print(f"Connecting to database at {db_path}...")
    
    now = datetime.datetime.now().isoformat()
    
    with sqlite3.connect(db_path) as conn:
        c = conn.cursor()
        c.execute("CREATE TABLE IF NOT EXISTS errors (dt TEXT, message TEXT, count INTEGER)")
        c.execute("CREATE TABLE IF NOT EXISTS api_metrics (dt TEXT, endpoint TEXT, avg_ms REAL)")
        
        # Insert error metrics with parameterized queries
        for msg, count in metrics.error_counts.items():
            c.execute("INSERT INTO errors VALUES (?, ?, ?)", (now, msg, count))
            
        # Insert API metrics
        for ep, times in metrics.api_latencies.items():
            avg = sum(times) / len(times)
            c.execute("INSERT INTO api_metrics VALUES (?, ?, ?)", (now, ep, avg))
        
        conn.commit()

    # Generate HTML report
    _generate_html_report(metrics, report_path)

def _generate_html_report(metrics: ProcessedMetrics, report_path: str) -> None:
    """Helper to generate the HTML report file."""
    out = [
        "<html>",
        "<head><title>System Report</title></head>",
        "<body>",
        "<h1>Error Summary</h1>",
        "<ul>"
    ]
    
    for err_msg, count in metrics.error_counts.items():
        out.append(f"<li><b>{err_msg}</b>: {count} occurrences</li>")
    out.append("</ul>")

    out.append("<h2>API Latency</h2>")
    out.append("<table border='1'>")
    out.append("<tr><th>Endpoint</th><th>Avg (ms)</th></tr>")
    for ep, times in metrics.api_latencies.items():
        avg = sum(times) / len(times)
        out.append(f"<tr><td>{ep}</td><td>{round(avg, 1)}</td></tr>")
    out.append("</table>")

    out.append("<h2>Active Sessions</h2>")
    out.append(f"<p>{len(metrics.active_sessions)} user(s) currently active</p>")
    out.append("</body>")
    out.append("</html>")

    with open(report_path, "w") as f:
        f.write("\n".join(out))

def run_pipeline() -> None:
    """Main execution function for the pipeline."""
    entries = extract(LOG_FILE)
    metrics = transform(entries)
    load(metrics, DB_PATH)
    print(f"Job finished at {datetime.datetime.now()}")

if __name__ == "__main__":
    # Ensure log file exists for demonstration if it doesn't
    if not LOG_FILE.exists():
        with LOG_FILE.open("w") as f:
            f.write("2024-01-01 12:00:00 INFO User 42 logged in\n")
            f.write("2024-01-01 12:05:00 ERROR Database timeout\n")
            f.write("2024-01-01 12:05:05 ERROR Database timeout\n")
            f.write("2024-01-01 12:08:00 INFO API /users/profile took 250ms\n")
            f.write("2024-01-01 12:09:00 WARN Memory usage at 87%\n")
            f.write("2024-01-01 12:10:00 INFO User 42 logged out\n")
    
    run_pipeline()
