#!/usr/bin/env python3
"""
Refactored server log processing pipeline.

This module processes server logs, extracts metrics, stores them in a database,
and generates an HTML report. It follows ETL (Extract, Transform, Load) pattern
with proper security practices and configuration management.
"""

import datetime
import os
import re
import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, TypedDict, Union


# ============================================================================
# Configuration via environment variables
# ============================================================================

class Config:
    """Configuration manager that reads from environment variables."""
    
    @staticmethod
    def get_db_path() -> str:
        """Get database path from environment variable."""
        return os.environ.get("DB_PATH", "metrics.db")
    
    @staticmethod
    def get_log_file_path() -> str:
        """Get log file path from environment variable."""
        return os.environ.get("LOG_FILE", "server.log")
    
    @staticmethod
    def get_db_host() -> str:
        """Get database host from environment variable."""
        return os.environ.get("DB_HOST", "localhost")
    
    @staticmethod
    def get_db_port() -> int:
        """Get database port from environment variable."""
        try:
            return int(os.environ.get("DB_PORT", "5432"))
        except ValueError:
            return 5432
    
    @staticmethod
    def get_db_user() -> str:
        """Get database user from environment variable."""
        return os.environ.get("DB_USER", "admin")
    
    @staticmethod
    def get_db_pass() -> str:
        """Get database password from environment variable."""
        return os.environ.get("DB_PASS", "password123")


# ============================================================================
# Data models
# ============================================================================

@dataclass
class LogEntry:
    """Represents a parsed log entry."""
    timestamp: str
    level: str
    message: str


@dataclass
class ErrorEntry:
    """Represents an error log entry."""
    timestamp: str
    message: str


@dataclass
class UserActivityEntry:
    """Represents a user activity log entry."""
    timestamp: str
    user_id: str
    action: str


@dataclass
class ApiCallEntry:
    """Represents an API call log entry."""
    timestamp: str
    endpoint: str
    duration_ms: int


@dataclass
class WarningEntry:
    """Represents a warning log entry."""
    timestamp: str
    message: str


# ============================================================================
# Log parsing with regex
# ============================================================================

class LogParser:
    """Parser for server log lines using regex patterns."""
    
    # Regex patterns for different log types
    LOG_PATTERN = re.compile(
        r'^(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}:\d{2}) (\w+) (.+)$'
    )
    USER_ACTIVITY_PATTERN = re.compile(
        r'User (\d+) (logged in|logged out)'
    )
    API_CALL_PATTERN = re.compile(
        r'API (\S+) took (\d+)ms'
    )
    
    @staticmethod
    def parse_line(line: str) -> Optional[LogEntry]:
        """
        Parse a single log line into a LogEntry.
        
        Args:
            line: A line from the log file
            
        Returns:
            LogEntry if line matches expected format, None otherwise
        """
        match = LogParser.LOG_PATTERN.match(line.strip())
        if not match:
            return None
            
        date, time, level, message = match.groups()
        timestamp = f"{date} {time}"
        return LogEntry(timestamp=timestamp, level=level, message=message)
    
    @staticmethod
    def extract_error(entry: LogEntry) -> Optional[ErrorEntry]:
        """
        Extract error information from a log entry.
        
        Args:
            entry: Parsed log entry
            
        Returns:
            ErrorEntry if entry is an error, None otherwise
        """
        if entry.level == "ERROR":
            return ErrorEntry(timestamp=entry.timestamp, message=entry.message)
        return None
    
    @staticmethod
    def extract_user_activity(entry: LogEntry) -> Optional[UserActivityEntry]:
        """
        Extract user activity information from a log entry.
        
        Args:
            entry: Parsed log entry
            
        Returns:
            UserActivityEntry if entry contains user activity, None otherwise
        """
        if entry.level == "INFO" and "User" in entry.message:
            match = LogParser.USER_ACTIVITY_PATTERN.search(entry.message)
            if match:
                user_id, action = match.groups()
                return UserActivityEntry(
                    timestamp=entry.timestamp,
                    user_id=user_id,
                    action=action
                )
        return None
    
    @staticmethod
    def extract_api_call(entry: LogEntry) -> Optional[ApiCallEntry]:
        """
        Extract API call information from a log entry.
        
        Args:
            entry: Parsed log entry
            
        Returns:
            ApiCallEntry if entry contains API call, None otherwise
        """
        if entry.level == "INFO" and "API" in entry.message:
            match = LogParser.API_CALL_PATTERN.search(entry.message)
            if match:
                endpoint, duration = match.groups()
                return ApiCallEntry(
                    timestamp=entry.timestamp,
                    endpoint=endpoint,
                    duration_ms=int(duration)
                )
        return None
    
    @staticmethod
    def extract_warning(entry: LogEntry) -> Optional[WarningEntry]:
        """
        Extract warning information from a log entry.
        
        Args:
            entry: Parsed log entry
            
        Returns:
            WarningEntry if entry is a warning, None otherwise
        """
        if entry.level == "WARN":
            return WarningEntry(timestamp=entry.timestamp, message=entry.message)
        return None


# ============================================================================
# Extract phase
# ============================================================================

def extract_logs(log_file_path: str) -> List[LogEntry]:
    """
    Extract and parse logs from a file.
    
    Args:
        log_file_path: Path to the log file
        
    Returns:
        List of parsed log entries
    """
    entries = []
    
    if not os.path.exists(log_file_path):
        print(f"Warning: Log file not found at {log_file_path}")
        return entries
    
    try:
        with open(log_file_path, 'r') as f:
            for line in f:
                entry = LogParser.parse_line(line)
                if entry:
                    entries.append(entry)
    except IOError as e:
        print(f"Error reading log file: {e}")
    
    return entries


# ============================================================================
# Transform phase
# ============================================================================

def transform_logs(entries: List[LogEntry]) -> Tuple[
    Dict[str, int],
    Dict[str, List[int]],
    Dict[str, str]
]:
    """
    Transform log entries into aggregated metrics.
    
    Args:
        entries: List of parsed log entries
        
    Returns:
        Tuple containing:
        - error_counts: Dict mapping error messages to count
        - api_latencies: Dict mapping endpoints to list of durations
        - active_sessions: Dict mapping user IDs to login timestamps
    """
    error_counts = defaultdict(int)
    api_latencies = defaultdict(list)
    active_sessions = {}
    
    for entry in entries:
        # Process errors
        error = LogParser.extract_error(entry)
        if error:
            error_counts[error.message] += 1
        
        # Process user activity
        user_activity = LogParser.extract_user_activity(entry)
        if user_activity:
            if user_activity.action == "logged in":
                active_sessions[user_activity.user_id] = user_activity.timestamp
            elif user_activity.action == "logged out":
                active_sessions.pop(user_activity.user_id, None)
        
        # Process API calls
        api_call = LogParser.extract_api_call(entry)
        if api_call:
            api_latencies[api_call.endpoint].append(api_call.duration_ms)
    
    return dict(error_counts), dict(api_latencies), active_sessions


# ============================================================================
# Load phase (database operations)
# ============================================================================

class DatabaseManager:
    """Manages database connections and operations with parameterized queries."""
    
    def __init__(self, db_path: str):
        """
        Initialize database manager.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self.connection = None
    
    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
    
    def connect(self) -> None:
        """Establish database connection."""
        self.connection = sqlite3.connect(self.db_path)
        self._create_tables()
    
    def close(self) -> None:
        """Close database connection."""
        if self.connection:
            self.connection.close()
            self.connection = None
    
    def _create_tables(self) -> None:
        """Create necessary tables if they don't exist."""
        cursor = self.connection.cursor()
        
        # Create errors table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS errors (
                dt TEXT,
                message TEXT,
                count INTEGER
            )
        """)
        
        # Create api_metrics table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS api_metrics (
                dt TEXT,
                endpoint TEXT,
                avg_ms REAL
            )
        """)
        
        self.connection.commit()
    
    def insert_error_counts(self, error_counts: Dict[str, int]) -> None:
        """
        Insert error counts into database using parameterized queries.
        
        Args:
            error_counts: Dict mapping error messages to count
        """
        if not self.connection:
            raise RuntimeError("Database not connected")
        
        cursor = self.connection.cursor()
        current_time = datetime.datetime.now().isoformat()
        
        for message, count in error_counts.items():
            cursor.execute(
                "INSERT INTO errors VALUES (?, ?, ?)",
                (current_time, message, count)
            )
        
        self.connection.commit()
    
    def insert_api_metrics(self, api_latencies: Dict[str, List[int]]) -> None:
        """
        Insert API latency metrics into database using parameterized queries.
        
        Args:
            api_latencies: Dict mapping endpoints to list of durations
        """
        if not self.connection:
            raise RuntimeError("Database not connected")
        
        cursor = self.connection.cursor()
        current_time = datetime.datetime.now().isoformat()
        
        for endpoint, durations in api_latencies.items():
            avg_duration = sum(durations) / len(durations)
            cursor.execute(
                "INSERT INTO api_metrics VALUES (?, ?, ?)",
                (current_time, endpoint, avg_duration)
            )
        
        self.connection.commit()


# ============================================================================
# Report generation
# ============================================================================

def generate_html_report(
    error_counts: Dict[str, int],
    api_latencies: Dict[str, List[int]],
    active_sessions: Dict[str, str],
    output_path: str = "report.html"
) -> None:
    """
    Generate HTML report from metrics.
    
    Args:
        error_counts: Dict mapping error messages to count
        api_latencies: Dict mapping endpoints to list of durations
        active_sessions: Dict mapping user IDs to login timestamps
        output_path: Path where HTML report should be saved
    """
    html_parts = []
    
    # HTML header
    html_parts.append("""<!DOCTYPE html>
<html>
<head>
    <title>System Report</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; }
        h1 { color: #333; }
        h2 { color: #555; margin-top: 30px; }
        table { border-collapse: collapse; width: 50%; margin-top: 10px; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background-color: #f2f2f2; }
        ul { list-style-type: none; padding-left: 0; }
        li { margin: 5px 0; padding: 5px; background-color: #f9f9f9; }
    </style>
</head>
<body>
    <h1>System Report</h1>
    <p>Generated: """ + datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S") + """</p>
""")
    
    # Error summary
    html_parts.append("""    <h2>Error Summary</h2>
""")
    if error_counts:
        html_parts.append("""    <ul>
""")
        for err_msg, count in error_counts.items():
            html_parts.append(f"""        <li><b>{err_msg}</b>: {count} occurrences</li>
""")
        html_parts.append("""    </ul>
""")
    else:
        html_parts.append("""    <p>No errors found in logs.</p>
""")
    
    # API latency table
    html_parts.append("""    <h2>API Latency</h2>
""")
    if api_latencies:
        html_parts.append("""    <table>
        <tr>
            <th>Endpoint</th>
            <th>Avg (ms)</th>
        </tr>
""")
        for endpoint, durations in api_latencies.items():
            avg = sum(durations) / len(durations)
            html_parts.append(f"""        <tr>
            <td>{endpoint}</td>
            <td>{avg:.1f}</td>
        </tr>
""")
        html_parts.append("""    </table>
""")
    else:
        html_parts.append("""    <p>No API calls found in logs.</p>
""")
    
    # Active sessions
    html_parts.append(f"""    <h2>Active Sessions</h2>
    <p>{len(active_sessions)} user(s) currently active</p>
""")
    
    # HTML footer
    html_parts.append("""</body>
</html>""")
    
    # Write to file
    try:
        with open(output_path, 'w') as f:
            f.write(''.join(html_parts))
        print(f"Report generated: {output_path}")
    except IOError as e:
        print(f"Error writing report: {e}")


# ============================================================================
# Main pipeline
# ============================================================================

def run_pipeline() -> None:
    """Main ETL pipeline execution."""
    print("Starting log processing pipeline...")
    
    # Load configuration from environment
    config = Config()
    log_file_path = config.get_log_file_path()
    db_path = config.get_db_path()
    
    print(f"Configuration loaded:")
    print(f"  Log file: {log_file_path}")
    print(f"  Database: {db_path}")
    print(f"  DB Host: {config.get_db_host()}:{config.get_db_port()}")
    print(f"  DB User: {config.get_db_user()}")
    
    # Extract phase
    print("\nExtracting logs...")
    log_entries = extract_logs(log_file_path)
    print(f"  Extracted {len(log_entries)} log entries")
    
    # Transform phase
    print("Transforming logs...")
    error_counts, api_latencies, active_sessions = transform_logs(log_entries)
    print(f"  Found {len(error_counts)} unique errors")
    print(f"  Found {len(api_latencies)} API endpoints")
    print(f"  Found {len(active_sessions)} active sessions")
    
    # Load phase
    print("Loading data to database...")
    try:
        with DatabaseManager(db_path) as db:
            db.insert_error_counts(error_counts)
            db.insert_api_metrics(api_latencies)
        print("  Data loaded successfully")
    except Exception as e:
        print(f"  Error loading data: {e}")
        return
    
    # Generate report
    print("Generating report...")
    generate_html_report(error_counts, api_latencies, active_sessions)
    
    print(f"\nPipeline completed at {datetime.datetime.now()}")


def create_sample_log_file(log_file_path: str) -> None:
    """
    Create a sample log file for testing if it doesn't exist.
    
    Args:
        log_file_path: Path where log file should be created
    """
    if not os.path.exists(log_file_path):
        print(f"Creating sample log file at {log_file_path}")
        sample_logs = [
            "2024-01-01 12:00:00 INFO User 42 logged in",
            "2024-01-01 12:05:00 ERROR Database timeout",
            "2024-01-01 12:05:05 ERROR Database timeout",
            "2024-01-01 12:08:00 INFO API /users/profile took 250ms",
            "2024-01-01 12:09:00 WARN Memory usage at 87%",
            "2024-01-01 12:10:00 INFO User 42 logged out",
            "2024-01-01 12:11:00 INFO API /api/data took 120ms",
            "2024-01-01 12:12:00 INFO User 99 logged in",
            "2024-01-01 12:13:00 ERROR Permission denied for user 99",
            "2024-01-01 12:14:00 INFO API /api/data took 95ms",
        ]
        
        try:
            with open(log_file_path, 'w') as f:
                for line in sample_logs:
                    f.write(line + '\n')
            print("Sample log file created successfully")
        except IOError as e:
            print(f"Error creating sample log file: {e}")


# ============================================================================
# Entry point
# ============================================================================

if __name__ == "__main__":
    # Create sample log file if needed
    log_file_path = Config.get_log_file_path()
    create_sample_log_file(log_file_path)
    
    # Run the pipeline
    run_pipeline()