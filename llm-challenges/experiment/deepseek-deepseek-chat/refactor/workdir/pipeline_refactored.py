#!/usr/bin/env python3
"""
Refactored server log processing pipeline.

This script processes server logs, extracts metrics, stores them in a database,
and generates an HTML report. It follows ETL (Extract, Transform, Load) pattern
with proper separation of concerns.

Features:
- Configuration via environment variables
- SQL injection protection via parameterized queries
- Regex-based log parsing
- Type hints and comprehensive docstrings
- Modular, maintainable architecture
"""

import datetime
import os
import re
import sqlite3
from typing import Dict, List, Optional, Tuple, TypedDict


# ============================================================================
# Configuration
# ============================================================================

class Config:
    """Configuration manager using environment variables with fallback defaults."""
    
    @staticmethod
    def get_db_path() -> str:
        """Get database file path from environment variable."""
        return os.getenv("DB_PATH", "metrics.db")
    
    @staticmethod
    def get_log_file_path() -> str:
        """Get log file path from environment variable."""
        return os.getenv("LOG_FILE", "server.log")
    
    @staticmethod
    def get_db_host() -> str:
        """Get database host from environment variable."""
        return os.getenv("DB_HOST", "localhost")
    
    @staticmethod
    def get_db_port() -> int:
        """Get database port from environment variable."""
        try:
            return int(os.getenv("DB_PORT", "5432"))
        except ValueError:
            return 5432
    
    @staticmethod
    def get_db_user() -> str:
        """Get database user from environment variable."""
        return os.getenv("DB_USER", "admin")
    
    @staticmethod
    def get_db_pass() -> str:
        """Get database password from environment variable."""
        return os.getenv("DB_PASS", "password123")


# ============================================================================
# Data Models
# ============================================================================

class LogEntry(TypedDict, total=False):
    """Represents a parsed log entry with optional fields."""
    timestamp: str
    level: str
    type: str  # "ERR", "WARN", "USR", "API"
    message: Optional[str]
    user_id: Optional[str]
    action: Optional[str]
    endpoint: Optional[str]
    duration_ms: Optional[int]


class ErrorSummary(TypedDict):
    """Summary of error occurrences."""
    message: str
    count: int


class ApiMetric(TypedDict):
    """API endpoint performance metric."""
    endpoint: str
    avg_ms: float
    call_count: int


# ============================================================================
# Extract: Log Parsing
# ============================================================================

class LogParser:
    """Parses log files using regex patterns."""
    
    # Regex patterns for different log line types
    LOG_PATTERN = re.compile(
        r'(?P<date>\d{4}-\d{2}-\d{2}) '
        r'(?P<time>\d{2}:\d{2}:\d{2}) '
        r'(?P<level>\w+) '
        r'(?P<message>.*)'
    )
    
    USER_PATTERN = re.compile(
        r'User (?P<user_id>\d+) (?P<action>.*)'
    )
    
    API_PATTERN = re.compile(
        r'API (?P<endpoint>/\S+) took (?P<duration>\d+)ms'
    )
    
    @classmethod
    def parse_line(cls, line: str) -> Optional[LogEntry]:
        """
        Parse a single log line into a structured LogEntry.
        
        Args:
            line: Raw log line
            
        Returns:
            Parsed LogEntry or None if line doesn't match expected format
        """
        line = line.strip()
        if not line:
            return None
            
        # Match basic log pattern
        match = cls.LOG_PATTERN.match(line)
        if not match:
            return None
            
        timestamp = f"{match.group('date')} {match.group('time')}"
        level = match.group('level')
        message = match.group('message')
        
        entry: LogEntry = {
            'timestamp': timestamp,
            'level': level,
        }
        
        # Parse based on log level and content
        if level == 'ERROR':
            entry['type'] = 'ERR'
            entry['message'] = message
        elif level == 'WARN':
            entry['type'] = 'WARN'
            entry['message'] = message
        elif level == 'INFO':
            if 'User' in message:
                user_match = cls.USER_PATTERN.search(message)
                if user_match:
                    entry['type'] = 'USR'
                    entry['user_id'] = user_match.group('user_id')
                    entry['action'] = user_match.group('action')
            elif 'API' in message:
                api_match = cls.API_PATTERN.search(message)
                if api_match:
                    entry['type'] = 'API'
                    entry['endpoint'] = api_match.group('endpoint')
                    entry['duration_ms'] = int(api_match.group('duration'))
        
        return entry
    
    @classmethod
    def parse_file(cls, file_path: str) -> List[LogEntry]:
        """
        Parse an entire log file.
        
        Args:
            file_path: Path to log file
            
        Returns:
            List of parsed log entries
        """
        entries: List[LogEntry] = []
        
        if not os.path.exists(file_path):
            print(f"Warning: Log file not found: {file_path}")
            return entries
        
        try:
            with open(file_path, 'r') as f:
                for line_num, line in enumerate(f, 1):
                    try:
                        entry = cls.parse_line(line)
                        if entry:
                            entries.append(entry)
                    except Exception as e:
                        print(f"Warning: Failed to parse line {line_num}: {e}")
        except IOError as e:
            print(f"Error reading log file {file_path}: {e}")
        
        return entries
# ============================================================================
# Transform: Data Processing
# ============================================================================

class DataProcessor:
    """Processes parsed log entries into structured metrics."""
    
    @staticmethod
    def extract_error_summary(entries: List[LogEntry]) -> List[ErrorSummary]:
        """
        Extract error message counts from log entries.
        
        Args:
            entries: List of parsed log entries
            
        Returns:
            List of error summaries with counts
        """
        error_counts: Dict[str, int] = {}
        
        for entry in entries:
            if entry.get('type') == 'ERR' and 'message' in entry:
                message = entry['message']
                error_counts[message] = error_counts.get(message, 0) + 1
        
        return [
            {'message': msg, 'count': count}
            for msg, count in error_counts.items()
        ]
    
    @staticmethod
    def extract_api_metrics(entries: List[LogEntry]) -> List[ApiMetric]:
        """
        Extract API performance metrics from log entries.
        
        Args:
            entries: List of parsed log entries
            
        Returns:
            List of API metrics with average response times
        """
        endpoint_data: Dict[str, List[int]] = {}
        
        for entry in entries:
            if entry.get('type') == 'API' and 'endpoint' in entry and 'duration_ms' in entry:
                endpoint = entry['endpoint']
                duration = entry['duration_ms']
                endpoint_data.setdefault(endpoint, []).append(duration)
        
        metrics: List[ApiMetric] = []
        for endpoint, durations in endpoint_data.items():
            avg_ms = sum(durations) / len(durations)
            metrics.append({
                'endpoint': endpoint,
                'avg_ms': avg_ms,
                'call_count': len(durations)
            })
        
        return metrics
    
    @staticmethod
    def count_active_sessions(entries: List[LogEntry]) -> int:
        """
        Count active user sessions based on login/logout events.
        
        Args:
            entries: List of parsed log entries
            
        Returns:
            Number of currently active sessions
        """
        active_sessions: Dict[str, bool] = {}
        
        for entry in entries:
            if entry.get('type') == 'USR' and 'user_id' in entry and 'action' in entry:
                user_id = entry['user_id']
                action = entry['action']
                
                if 'logged in' in action:
                    active_sessions[user_id] = True
                elif 'logged out' in action and user_id in active_sessions:
                    del active_sessions[user_id]
        
        return len(active_sessions)


# ============================================================================
# Load: Database Operations
# ============================================================================

class DatabaseManager:
    """Manages database connections and operations with SQL injection protection."""
    
    def __init__(self, db_path: str):
        """
        Initialize database manager.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self.connection: Optional[sqlite3.Connection] = None
    
    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
    
    def connect(self) -> None:
        """Establish database connection."""
        try:
            self.connection = sqlite3.connect(self.db_path)
            self._create_tables()
        except sqlite3.Error as e:
            print(f"Database connection error: {e}")
            raise
    
    def close(self) -> None:
        """Close database connection."""
        if self.connection:
            self.connection.close()
            self.connection = None
    
    def _create_tables(self) -> None:
        """Create necessary tables if they don't exist."""
        if not self.connection:
            raise RuntimeError("Database not connected")
        
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
    
    def store_error_summary(self, errors: List[ErrorSummary]) -> None:
        """
        Store error summaries in database using parameterized queries.
        
        Args:
            errors: List of error summaries
        """
        if not self.connection:
            raise RuntimeError("Database not connected")
        
        cursor = self.connection.cursor()
        current_time = datetime.datetime.now().isoformat()
        
        for error in errors:
            # Parameterized query to prevent SQL injection
            cursor.execute(
                "INSERT INTO errors VALUES (?, ?, ?)",
                (current_time, error['message'], error['count'])
            )
        
        self.connection.commit()
    
    def store_api_metrics(self, metrics: List[ApiMetric]) -> None:
        """
        Store API metrics in database using parameterized queries.
        
        Args:
            metrics: List of API metrics
        """
        if not self.connection:
            raise RuntimeError("Database not connected")
        
        cursor = self.connection.cursor()
        current_time = datetime.datetime.now().isoformat()
        
        for metric in metrics:
            # Parameterized query to prevent SQL injection
            cursor.execute(
                "INSERT INTO api_metrics VALUES (?, ?, ?)",
                (current_time, metric['endpoint'], metric['avg_ms'])
            )
        
        self.connection.commit()
# ============================================================================
# Report Generation
# ============================================================================

class ReportGenerator:
    """Generates HTML reports from processed data."""
    
    @staticmethod
    def generate_html_report(
        errors: List[ErrorSummary],
        api_metrics: List[ApiMetric],
        active_sessions: int
    ) -> str:
        """
        Generate HTML report with error summary, API latency, and active sessions.
        
        Args:
            errors: List of error summaries
            api_metrics: List of API metrics
            active_sessions: Number of active sessions
            
        Returns:
            HTML report as string
        """
        html = """<!DOCTYPE html>
<html>
<head>
    <title>System Report</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; }
        h1 { color: #333; }
        h2 { color: #555; margin-top: 30px; }
        table { border-collapse: collapse; width: 100%; max-width: 600px; }
        th, td { border: 1px solid #ddd; padding: 12px; text-align: left; }
        th { background-color: #f2f2f2; }
        ul { list-style-type: none; padding-left: 0; }
        li { margin-bottom: 10px; padding: 10px; background-color: #f9f9f9; border-left: 4px solid #e74c3c; }
        .timestamp { color: #777; font-size: 0.9em; margin-top: 20px; }
    </style>
</head>
<body>
    <h1>Error Summary</h1>
"""
        
        if errors:
            html += "    <ul>\n"
            for error in errors:
                html += f'        <li><b>{error["message"]}</b>: {error["count"]} occurrence(s)</li>\n'
            html += "    </ul>\n"
        else:
            html += "    <p>No errors found.</p>\n"
        
        html += """
    <h2>API Latency</h2>
"""
        if api_metrics:
            html += """    <table>
        <tr>
            <th>Endpoint</th>
            <th>Average Response Time (ms)</th>
            <th>Call Count</th>
        </tr>
"""
            for metric in api_metrics:
                html += f'        <tr><td>{metric["endpoint"]}</td><td>{metric["avg_ms"]:.1f}</td><td>{metric["call_count"]}</td></tr>\n'
            html += "    </table>\n"
        else:
            html += "    <p>No API calls recorded.</p>\n"
        
        html += f"""
    <h2>Active Sessions</h2>
    <p>{active_sessions} user(s) currently active</p>
    
    <div class="timestamp">
        Report generated: {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
    </div>
</body>
</html>"""
        
        return html
    
    @staticmethod
    def save_report(html: str, output_path: str = "report.html") -> None:
        """
        Save HTML report to file.
        
        Args:
            html: HTML content
            output_path: Path to save report
        """
        try:
            with open(output_path, 'w') as f:
                f.write(html)
            print(f"Report saved to {output_path}")
        except IOError as e:
            print(f"Error saving report: {e}")


# ============================================================================
# Main Pipeline
# ============================================================================

def run_pipeline() -> None:
    """
    Main pipeline execution function.
    
    Orchestrates the ETL process:
    1. Extract: Parse log file
    2. Transform: Process data into metrics
    3. Load: Store metrics in database
    4. Generate: Create HTML report
    """
    print("Starting log processing pipeline...")
    
    # Configuration
    config = Config()
    db_path = config.get_db_path()
    log_file = config.get_log_file_path()
    
    print(f"Configuration:")
    print(f"  Database: {db_path}")
    print(f"  Log file: {log_file}")
    print(f"  DB Host: {config.get_db_host()}:{config.get_db_port()}")
    print(f"  DB User: {config.get_db_user()}")
    
    # Extract: Parse log file
    print("\n[EXTRACT] Parsing log file...")
    entries = LogParser.parse_file(log_file)
    print(f"  Parsed {len(entries)} log entries")
    
    # Transform: Process data
    print("\n[TRANSFORM] Processing data...")
    errors = DataProcessor.extract_error_summary(entries)
    api_metrics = DataProcessor.extract_api_metrics(entries)
    active_sessions = DataProcessor.count_active_sessions(entries)
    
    print(f"  Found {len(errors)} unique error types")
    print(f"  Found {len(api_metrics)} API endpoints")
    print(f"  Active sessions: {active_sessions}")
    
    # Load: Store in database
    print("\n[LOAD] Storing metrics in database...")
    try:
        with DatabaseManager(db_path) as db:
            db.store_error_summary(errors)
            db.store_api_metrics(api_metrics)
        print("  Data stored successfully")
    except Exception as e:
        print(f"  Error storing data: {e}")
        return
    
    # Generate report
    print("\n[GENERATE] Creating HTML report...")
    html = ReportGenerator.generate_html_report(errors, api_metrics, active_sessions)
    ReportGenerator.save_report(html)
    
    print(f"\nPipeline completed at {datetime.datetime.now()}")


def create_sample_log_file(file_path: str) -> None:
    """
    Create a sample log file if it doesn't exist.
    
    Args:
        file_path: Path to log file
    """
    if os.path.exists(file_path):
        return
    
    sample_logs = [
        "2024-01-01 12:00:00 INFO User 42 logged in",
        "2024-01-01 12:05:00 ERROR Database timeout",
        "2024-01-01 12:05:05 ERROR Database timeout",
        "2024-01-01 12:08:00 INFO API /users/profile took 250ms",
        "2024-01-01 12:09:00 WARN Memory usage at 87%",
        "2024-01-01 12:10:00 INFO User 42 logged out",
        "2024-01-01 12:11:00 INFO API /api/data took 120ms",
        "2024-01-01 12:12:00 INFO User 99 logged in",
        "2024-01-01 12:13:00 ERROR Permission denied",
        "2024-01-01 12:14:00 INFO API /users/profile took 180ms",
    ]
    
    try:
        with open(file_path, 'w') as f:
            for log in sample_logs:
                f.write(log + "\n")
        print(f"Created sample log file: {file_path}")
    except IOError as e:
        print(f"Error creating sample log file: {e}")


if __name__ == "__main__":
    # Create sample log file if it doesn't exist
    log_file_path = Config.get_log_file_path()
    create_sample_log_file(log_file_path)
    
    # Run the pipeline
    run_pipeline()