"""
Log processor pipeline: Extract → Transform → Load

This script reads server logs, aggregates metrics, and generates an HTML report.
It uses environment variables for configuration and parameterized queries for safety.

Environment Variables:
    DB_PATH: Path to the SQLite database file (default: metrics.db)
    LOG_FILE: Path to the server log file (default: server.log)
    REPORT_FILE: Path to the output HTML report (default: report.html)
    DB_HOST: Database host (for logging only, sqlite3 uses file)
    DB_PORT: Database port (for logging only)
    DB_USER: Database user (for logging only)
"""

import datetime
import os
import re
import sqlite3
from dataclasses import dataclass
from typing import Optional


# =============================================================================
# Configuration
# =============================================================================

@dataclass(frozen=True)
class Config:
    """Configuration loaded from environment variables."""
    db_path: str
    log_file: str
    report_file: str
    db_host: str
    db_port: int
    db_user: str

    @classmethod
    def from_env(cls) -> "Config":
        """Create config instance from environment variables."""
        return cls(
            db_path=os.getenv("DB_PATH", "metrics.db"),
            log_file=os.getenv("LOG_FILE", "server.log"),
            report_file=os.getenv("REPORT_FILE", "report.html"),
            db_host=os.getenv("DB_HOST", "localhost"),
            db_port=int(os.getenv("DB_PORT", "5432")),
            db_user=os.getenv("DB_USER", "admin"),
        )


CONFIG = Config.from_env()

# Log line patterns (regex)
LOG_LINE_PATTERN = re.compile(
    r"^(?P<date>[0-9]{4}-[0-9]{2}-[0-9]{2})\s+"  # Date: 2024-01-01
    r"(?P<time>[0-9]{2}:[0-9]{2}:[0-9]{2})\s+"   # Time: 12:00:00
    r"(?P<level>ERROR|WARN|INFO)\s+"              # Level
    r"(?P<message>.*)$"                           # Rest of message
)

USER_PATTERN = re.compile(r"User\s+(?P<user_id>\d+)\s+(?P<action>.+)")
API_PATTERN = re.compile(r"API\s+(?P<endpoint>/[^\s]+).*took\s+(?P<duration>\d+)ms")


# =============================================================================
# Extract Module
# =============================================================================

def parse_log_line(line: str) -> Optional[dict]:
    """
    Parse a single log line into structured data.
    
    Returns a dict with parsed fields or None if the line doesn't match expected format.
    
    Expected log format:
        2024-01-01 12:00:00 INFO User 42 logged in
        2024-01-01 12:05:00 ERROR Database timeout
        2024-01-01 12:08:00 INFO API /users/profile took 250ms
        2024-01-01 12:09:00 WARN Memory usage at 87%
    """
    match = LOG_LINE_PATTERN.match(line.strip())
    if not match:
        return None
    
    level = match.group("level")
    timestamp = f"{match.group('date')} {match.group('time')}"
    message = match.group("message")
    
    parsed = {
        "timestamp": timestamp,
        "level": level,
        "raw_message": message,
    }
    
    # Extract structured data based on level
    if level == "ERROR":
        parsed["error_message"] = message
    elif level == "WARN":
        parsed["warning_message"] = message
    elif level == "INFO":
        parsed["type"] = "unknown"
        
        # Try to match user actions
        user_match = USER_PATTERN.match(message)
        if user_match:
            parsed["type"] = "user"
            parsed["user_id"] = user_match.group("user_id")
            parsed["user_action"] = user_match.group("action")
        else:
            # Try to match API calls
            api_match = API_PATTERN.match(message)
            if api_match:
                parsed["type"] = "api"
                parsed["endpoint"] = api_match.group("endpoint")
                parsed["duration_ms"] = int(api_match.group("duration"))
    
    return parsed


def extract_logs(log_file: str) -> list[dict]:
    """
    Extract and parse all valid log entries from a log file.
    
    Args:
        log_file: Path to the log file
        
    Returns:
        List of parsed log entries
    """
    entries = []
    
    if not os.path.exists(log_file):
        return entries
    
    with open(log_file, "r") as f:
        for line in f:
            parsed = parse_log_line(line)
            if parsed:
                entries.append(parsed)
    
    return entries


# =============================================================================
# Transform Module
# =============================================================================

def transform_logs(entries: list[dict]) -> tuple[list[dict], dict[str, int], dict[str, list[int]]]:
    """
    Transform parsed log entries into aggregated metrics.
    
    Args:
        entries: List of parsed log entries
        
    Returns:
        Tuple of (error_list, session_dict, endpoint_stats)
        - error_list: List of error records with timestamp and message
        - session_dict: Dict mapping user_id to last login timestamp
        - endpoint_stats: Dict mapping endpoint to list of durations
    """
    errors = []
    sessions = {}
    api_calls = {}
    
    for entry in entries:
        level = entry["level"]
        
        if level == "ERROR":
            errors.append({
                "timestamp": entry["timestamp"],
                "message": entry["error_message"],
            })
        
        elif level == "INFO" and entry.get("type") == "user":
            user_id = entry["user_id"]
            action = entry["user_action"]
            
            if "logged in" in action:
                sessions[user_id] = entry["timestamp"]
            elif "logged out" in action and user_id in sessions:
                sessions.pop(user_id)
        
        elif level == "INFO" and entry.get("type") == "api":
            endpoint = entry["endpoint"]
            duration = entry["duration_ms"]
            
            if endpoint not in api_calls:
                api_calls[endpoint] = []
            api_calls[endpoint].append(duration)
        
        elif level == "WARN":
            errors.append({
                "timestamp": entry["timestamp"],
                "message": f"[WARN] {entry['warning_message']}",
            })
    
    return errors, sessions, api_calls


def aggregate_errors(errors: list[dict]) -> dict[str, int]:
    """
    Aggregate error messages with their counts.
    
    Args:
        errors: List of error records
        
    Returns:
        Dict mapping error message to occurrence count
    """
    counts: dict[str, int] = {}
    for err in errors:
        msg = err["message"]
        counts[msg] = counts.get(msg, 0) + 1
    return counts


def calculate_endpoint_stats(endpoint_data: dict[str, list[int]]) -> dict[str, float]:
    """
    Calculate average latency per endpoint.
    
    Args:
        endpoint_data: Dict mapping endpoint to list of durations
        
    Returns:
        Dict mapping endpoint to average duration
    """
    return {
        endpoint: sum(durations) / len(durations)
        for endpoint, durations in endpoint_data.items()
    }


# =============================================================================
# Load Module
# =============================================================================

class DatabaseManager:
    """Context manager for SQLite database connections with parameterized queries."""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn: Optional[sqlite3.Connection] = None
        self.cursor: Optional[sqlite3.Cursor] = None
    
    def __enter__(self) -> "DatabaseManager":
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()
        self._init_schema()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self.conn:
            self.conn.close()
    
    def _init_schema(self) -> None:
        """Create required tables if they don't exist."""
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS errors (
                dt TEXT,
                message TEXT,
                count INTEGER
            )
        """)
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS api_metrics (
                dt TEXT,
                endpoint TEXT,
                avg_ms REAL
            )
        """)
        self.conn.commit()
    
    def insert_error(self, timestamp: str, message: str, count: int) -> None:
        """
        Insert an error record using parameterized query.
        
        Args:
            timestamp: Timestamp of when the error was recorded
            message: Error message text
            count: Number of occurrences
        """
        self.cursor.execute(
            "INSERT INTO errors (dt, message, count) VALUES (?, ?, ?)",
            (timestamp, message, count),
        )
    
    def insert_api_metric(self, timestamp: str, endpoint: str, avg_ms: float) -> None:
        """
        Insert an API metric record using parameterized query.
        
        Args:
            timestamp: Timestamp of when the metric was recorded
            endpoint: API endpoint path
            avg_ms: Average latency in milliseconds
        """
        self.cursor.execute(
            "INSERT INTO api_metrics (dt, endpoint, avg_ms) VALUES (?, ?, ?)",
            (timestamp, endpoint, avg_ms),
        )


def load_to_database(
    errors: list[dict],
    endpoint_stats: dict[str, float],
    db_path: str,
) -> None:
    """
    Load aggregated metrics into the database.
    
    Args:
        errors: List of error records with counts
        endpoint_stats: Dict of endpoint to average latency
        db_path: Path to the SQLite database file
    """
    current_time = datetime.datetime.now().isoformat()
    
    with DatabaseManager(db_path) as db:
        # Insert error aggregations
        for err in errors:
            db.insert_error(
                timestamp=current_time,
                message=err["message"],
                count=err["count"],
            )
        
        # Insert API metrics
        for endpoint, avg in endpoint_stats.items():
            db.insert_api_metric(
                timestamp=current_time,
                endpoint=endpoint,
                avg_ms=avg,
            )


# =============================================================================
# Report Generation
# =============================================================================

def generate_report(
    error_counts: dict[str, int],
    endpoint_stats: dict[str, list[int]],
    active_sessions: dict[str, str],
) -> str:
    """
    Generate an HTML report.
    
    Args:
        error_counts: Dict mapping error message to count
        endpoint_stats: Dict mapping endpoint to list of durations
        active_sessions: Dict of active user sessions
        
    Returns:
        HTML report as a string
    """
    # Error Summary
    error_html = []
    for msg, count in error_counts.items():
        error_html.append(f"<li><b>{msg}</b>: {count} occurrences</li>")
    
    # API Latency Table
    api_rows = []
    for endpoint, durations in endpoint_stats.items():
        avg = sum(durations) / len(durations)
        api_rows.append(f"<tr><td>{endpoint}</td><td>{round(avg, 1)}</td></tr>")
    
    # Build HTML
    html = [
        "<html>",
        "<head><title>System Report</title></head>",
        "<body>",
        "<h1>Error Summary</h1>",
        "<ul>",
        *error_html,
        "</ul>",
        "<h2>API Latency</h2>",
        "<table border='1'>",
        "<tr><th>Endpoint</th><th>Avg (ms)</th></tr>",
        *api_rows,
        "</table>",
        "<h2>Active Sessions</h2>",
        f"<p>{len(active_sessions)} user(s) currently active</p>",
        "</body>",
        "</html>",
    ]
    
    return "\n".join(html)


def save_report(report_html: str, report_file: str) -> None:
    """
    Save the HTML report to a file.
    
    Args:
        report_html: HTML content as a string
        report_file: Output file path
    """
    with open(report_file, "w") as f:
        f.write(report_html)


# =============================================================================
# Main Pipeline
# =============================================================================

def run_pipeline() -> None:
    """
    Run the complete ETL pipeline: Extract → Transform → Load.
    
    This function orchestrates the entire log processing pipeline:
    1. Extract: Read and parse log files
    2. Transform: Aggregate metrics
    3. Load: Store in database and generate report
    """
    # ----- EXTRACT -----
    print(f"Reading logs from {CONFIG.log_file}...")
    raw_entries = extract_logs(CONFIG.log_file)
    print(f"Parsed {len(raw_entries)} log entries")
    
    # ----- TRANSFORM -----
    print("Transforming log entries into metrics...")
    errors, sessions, api_calls = transform_logs(raw_entries)
    error_aggregates = aggregate_errors(errors)
    endpoint_stats = calculate_endpoint_stats(api_calls)
    
    # ----- LOAD -----
    print(f"Connecting to {CONFIG.db_host}:{CONFIG.db_port} as {CONFIG.db_user}...")
    print(f"Storing metrics in {CONFIG.db_path}...")
    load_to_database(errors, endpoint_stats, CONFIG.db_path)
    
    # ----- REPORT -----
    print(f"Generating report at {CONFIG.report_file}...")
    report_html = generate_report(error_aggregates, api_calls, sessions)
    save_report(report_html, CONFIG.report_file)
    
    print(f"Pipeline finished at {datetime.datetime.now().isoformat()}")


if __name__ == "__main__":
    # For demo purposes, create a sample log file if none exists
    if not os.path.exists(CONFIG.log_file):
        print(f"Creating sample log file at {CONFIG.log_file}...")
        os.makedirs(os.path.dirname(CONFIG.log_file) or ".", exist_ok=True)
        with open(CONFIG.log_file, "w") as f:
            f.write("2024-01-01 12:00:00 INFO User 42 logged in\n")
            f.write("2024-01-01 12:05:00 ERROR Database timeout\n")
            f.write("2024-01-01 12:05:05 ERROR Database timeout\n")
            f.write("2024-01-01 12:08:00 INFO API /users/profile took 250ms\n")
            f.write("2024-01-01 12:09:00 WARN Memory usage at 87%\n")
            f.write("2024-01-01 12:10:00 INFO User 42 logged out\n")
    
    run_pipeline()
