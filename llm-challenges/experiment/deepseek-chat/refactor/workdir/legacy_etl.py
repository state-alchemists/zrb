#!/usr/bin/env python3
"""
ETL (Extract, Transform, Load) pipeline for processing server logs.

This module extracts error and user action data from server logs,
transforms the data into structured format, and loads it into
a simulated database while generating HTML reports.
"""

import datetime
import os
import re
from typing import Dict, List, Optional, TypedDict, Union
from dataclasses import dataclass


# Configuration using environment variables with defaults
class Config:
    """Configuration for the ETL pipeline."""
    
    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_USER: str = os.getenv("DB_USER", "admin")
    LOG_FILE: str = os.getenv("LOG_FILE", "server.log")
    REPORT_FILE: str = os.getenv("REPORT_FILE", "report.html")


@dataclass
class LogEntry:
    """Represents a parsed log entry."""
    timestamp: str
    log_type: str
    message: str
    user_id: Optional[str] = None


@dataclass
class ProcessedEntry:
    """Represents a processed log entry ready for reporting."""
    date: str
    entry_type: str
    message: str
    user_id: Optional[str] = None


def extract_logs(log_file_path: str) -> List[str]:
    """
    Extract raw log lines from a log file.
    
    Args:
        log_file_path: Path to the log file
        
    Returns:
        List of raw log lines as strings
        
    Raises:
        FileNotFoundError: If the log file doesn't exist
    """
    if not os.path.exists(log_file_path):
        raise FileNotFoundError(f"Log file not found: {log_file_path}")
    
    with open(log_file_path, "r") as f:
        return f.readlines()


def parse_log_line(line: str) -> Optional[LogEntry]:
    """
    Parse a single log line using regex.
    
    Expected format: "YYYY-MM-DD HH:MM:SS TYPE Message content"
    
    Args:
        line: Raw log line string
        
    Returns:
        LogEntry object if parsing successful, None otherwise
    """
    # Regex pattern for log parsing
    # Groups: 1=date, 2=time, 3=type, 4=message
    pattern = r'^(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2}:\d{2})\s+(\w+)\s+(.+)$'
    match = re.match(pattern, line.strip())
    
    if not match:
        return None
    
    date_str = match.group(1)
    time_str = match.group(2)
    log_type = match.group(3)
    message = match.group(4)
    
    timestamp = f"{date_str} {time_str}"
    
    # Extract user ID if present in INFO messages
    user_id = None
    if log_type == "INFO" and "User" in message:
        user_match = re.search(r'User\s+(\d+)', message)
        if user_match:
            user_id = user_match.group(1)
    
    return LogEntry(
        timestamp=timestamp,
        log_type=log_type,
        message=message,
        user_id=user_id
    )


def transform_logs(raw_logs: List[str]) -> List[ProcessedEntry]:
    """
    Transform raw log lines into structured data.
    
    Args:
        raw_logs: List of raw log line strings
        
    Returns:
        List of processed log entries
    """
    processed_entries: List[ProcessedEntry] = []
    
    for line in raw_logs:
        log_entry = parse_log_line(line)
        
        if not log_entry:
            continue
        
        # Determine entry type based on log type and content
        entry_type = log_entry.log_type
        if log_entry.log_type == "INFO" and log_entry.user_id:
            entry_type = "USER_ACTION"
        
        processed_entry = ProcessedEntry(
            date=log_entry.timestamp,
            entry_type=entry_type,
            message=log_entry.message,
            user_id=log_entry.user_id
        )
        
        processed_entries.append(processed_entry)
    
    return processed_entries


def load_to_database(entries: List[ProcessedEntry], config: Config) -> None:
    """
    Simulate loading data to database.
    
    Args:
        entries: List of processed log entries
        config: Configuration object
    """
    print(f"Connecting to {config.DB_HOST} as {config.DB_USER}...")
    print(f"Loaded {len(entries)} log entries to database")
    
    # In a real implementation, this would connect to an actual database
    # and insert the entries


def generate_report(entries: List[ProcessedEntry], report_file: str) -> None:
    """
    Generate HTML report from processed log entries.
    
    Args:
        entries: List of processed log entries
        report_file: Path to output HTML report file
    """
    # Count error occurrences
    error_counts: Dict[str, int] = {}
    
    for entry in entries:
        if entry.entry_type == "ERROR":
            if entry.message not in error_counts:
                error_counts[entry.message] = 0
            error_counts[entry.message] += 1
    
    # Generate HTML report
    html_lines = [
        "<!DOCTYPE html>",
        "<html>",
        "<head>",
        "<title>Server Log Report</title>",
        "<style>",
        "body { font-family: Arial, sans-serif; margin: 40px; }",
        "h1 { color: #333; }",
        "ul { list-style-type: none; padding: 0; }",
        "li { padding: 8px; margin: 5px 0; background: #f5f5f5; border-radius: 4px; }",
        "</style>",
        "</head>",
        "<body>",
        "<h1>Server Log Error Report</h1>",
        f"<p>Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>",
        f"<p>Total entries processed: {len(entries)}</p>"
    ]
    
    if error_counts:
        html_lines.append("<h2>Error Summary</h2>")
        html_lines.append("<ul>")
        for error_msg, count in sorted(error_counts.items(), key=lambda x: x[1], reverse=True):
            html_lines.append(f"<li><strong>{error_msg}</strong>: {count} occurrence(s)</li>")
        html_lines.append("</ul>")
    else:
        html_lines.append("<p>No errors found in the logs.</p>")
    
    # Add user action summary if present
    user_actions = [e for e in entries if e.entry_type == "USER_ACTION"]
    if user_actions:
        html_lines.append("<h2>User Actions</h2>")
        html_lines.append("<ul>")
        for action in user_actions:
            html_lines.append(f"<li>{action.date}: User {action.user_id} - {action.message}</li>")
        html_lines.append("</ul>")
    
    html_lines.append("</body>")
    html_lines.append("</html>")
    
    # Write report to file
    with open(report_file, "w") as f:
        f.write("\n".join(html_lines))
    
    print(f"Report generated: {report_file}")


def create_dummy_logs(log_file_path: str) -> None:
    """
    Create dummy log file for testing if it doesn't exist.
    
    Args:
        log_file_path: Path to the log file to create
    """
    dummy_logs = [
        "2023-10-01 10:00:00 INFO User 123 logged in\n",
        "2023-10-01 10:05:00 ERROR Connection failed\n",
        "2023-10-01 10:10:00 ERROR Connection failed\n",
        "2023-10-01 10:15:00 INFO System backup completed\n",
        "2023-10-01 10:20:00 ERROR Database timeout\n",
        "2023-10-01 10:25:00 INFO User 456 logged out\n",
        "2023-10-01 10:30:00 WARNING High memory usage detected\n",
    ]
    
    with open(log_file_path, "w") as f:
        f.writelines(dummy_logs)
    
    print(f"Created dummy log file: {log_file_path}")


def run_etl_pipeline(config: Config) -> None:
    """
    Main ETL pipeline execution function.
    
    Args:
        config: Configuration object
    """
    print("Starting ETL pipeline...")
    
    try:
        # Extract phase
        print(f"Extracting logs from {config.LOG_FILE}...")
        raw_logs = extract_logs(config.LOG_FILE)
        print(f"Extracted {len(raw_logs)} log lines")
        
        # Transform phase
        print("Transforming log data...")
        processed_entries = transform_logs(raw_logs)
        print(f"Transformed {len(processed_entries)} entries")
        
        # Load phase
        load_to_database(processed_entries, config)
        
        # Generate report
        print(f"Generating report to {config.REPORT_FILE}...")
        generate_report(processed_entries, config.REPORT_FILE)
        
        print("ETL pipeline completed successfully!")
        
    except FileNotFoundError as e:
        print(f"Error: {e}")
        print("Please ensure the log file exists or run with --create-dummy flag")
    except Exception as e:
        print(f"Unexpected error during ETL pipeline: {e}")
        raise


def main(create_dummy: bool = False) -> None:
    """
    Main entry point for the ETL script.
    
    Args:
        create_dummy: If True, create dummy log file before running ETL
    """
    config = Config()
    
    # Create dummy logs if requested or if log file doesn't exist
    if create_dummy or not os.path.exists(config.LOG_FILE):
        print("Creating dummy log data...")
        create_dummy_logs(config.LOG_FILE)
    
    # Run the ETL pipeline
    run_etl_pipeline(config)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="ETL pipeline for server logs")
    parser.add_argument(
        "--create-dummy",
        action="store_true",
        help="Create dummy log file before running ETL"
    )
    
    args = parser.parse_args()
    main(create_dummy=args.create_dummy)
