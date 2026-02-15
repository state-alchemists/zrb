"""
ETL Pipeline for Log Processing.

This module implements a modular ETL (Extract, Transform, Load) pipeline
for parsing server logs and generating error reports.

Configuration is managed via environment variables:
    - DB_HOST: Database host (default: localhost)
    - DB_USER: Database user (default: admin)
    - DB_PASS: Database password (default: password123)
    - LOG_FILE: Path to log file (default: server.log)
"""

import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List


# =============================================================================
# Configuration
# =============================================================================

@dataclass(frozen=True)
class Config:
    """Application configuration loaded from environment variables."""
    db_host: str
    db_user: str
    db_pass: str
    log_file: Path

    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables with defaults."""
        return cls(
            db_host=os.getenv("DB_HOST", "localhost"),
            db_user=os.getenv("DB_USER", "admin"),
            db_pass=os.getenv("DB_PASS", "password123"),
            log_file=Path(os.getenv("LOG_FILE", "server.log")),
        )


# =============================================================================
# Data Models
# =============================================================================

@dataclass
class LogEntry:
    """Represents a parsed log entry."""
    timestamp: datetime
    entry_type: str  # "ERR" or "USR"
    message: str | None = None
    user_id: str | None = None


@dataclass
class ErrorSummary:
    """Summary of error occurrences."""
    message: str
    count: int


# =============================================================================
# Extract
# =============================================================================

def extract_logs(config: Config) -> List[str]:
    """
    Extract raw log lines from the log file.
    
    Args:
        config: Application configuration.
    
    Returns:
        List of raw log lines. Empty list if file doesn't exist.
    """
    if not config.log_file.exists():
        return []
    
    return config.log_file.read_text(encoding="utf-8").strip().split("\n")


# =============================================================================
# Transform
# =============================================================================

LogPattern = re.compile(
    r"^(?P<date>\d{4}-\d{2}-\d{2})\s+"
    r"(?P<time>\d{2}:\d{2}:\d{2})\s+"
    r"(?P<level>\w+)\s+"
    r"(?P<content>.*)$"
)

UserPattern = re.compile(r"User\s+(?P<user_id>\d+)")


def parse_log_line(line: str) -> LogEntry | None:
    """
    Parse a single log line into a structured LogEntry.
    
    Args:
        line: Raw log line.
    
    Returns:
        LogEntry if parsing succeeds, None otherwise.
    """
    match = LogPattern.match(line.strip())
    if not match:
        return None

    try:
        timestamp = datetime.fromisoformat(
            f"{match['date']} {match['time']}"
        )
    except ValueError:
        return None

    level = match["level"]
    content = match["content"]

    if level == "ERROR":
        return LogEntry(
            timestamp=timestamp,
            entry_type="ERR",
            message=content,
        )
    elif level == "INFO" and "User" in content:
        user_match = UserPattern.search(content)
        if user_match:
            return LogEntry(
                timestamp=timestamp,
                entry_type="USR",
                user_id=user_match["user_id"],
            )
    
    return None


def transform_logs(raw_lines: List[str]) -> List[LogEntry]:
    """
    Transform raw log lines into structured LogEntry objects.
    
    Args:
        raw_lines: List of raw log lines.
    
    Returns:
        List of parsed LogEntry objects.
    """
    entries: List[LogEntry] = []
    for line in raw_lines:
        entry = parse_log_line(line)
        if entry:
            entries.append(entry)
    return entries


# =============================================================================
# Load
# =============================================================================

def upload_to_database(entries: List[LogEntry], config: Config) -> None:
    """
    Upload processed entries to the database.
    
    Args:
        entries: List of LogEntry objects to upload.
        config: Application configuration.
    
    Note:
        Database insertion logic is currently a placeholder.
    """
    print(f"Connecting to {config.db_host} as {config.db_user}...")
    # NOTE: Actual database insertion logic would go here


def generate_error_summary(entries: List[LogEntry]) -> List[ErrorSummary]:
    """
    Aggregate error entries by message.
    
    Args:
        entries: List of LogEntry objects.
    
    Returns:
        List of ErrorSummary objects sorted by count (descending).
    """
    error_counts: Dict[str, int] = {}
    for entry in entries:
        if entry.entry_type == "ERR" and entry.message:
            error_counts[entry.message] = error_counts.get(entry.message, 0) + 1
    
    return [
        ErrorSummary(message=msg, count=count)
        for msg, count in sorted(
            error_counts.items(),
            key=lambda x: x[1],
            reverse=True,
        )
    ]


def generate_html_report(summaries: List[ErrorSummary], output_path: Path) -> None:
    """
    Generate an HTML report from error summaries.
    
    Args:
        summaries: List of ErrorSummary objects.
        output_path: Path to write the HTML report.
    """
    lines: List[str] = [
        "<html>",
        "<head><title>System Report</title></head>",
        "<body>",
        "<h1>Error Summary</h1>",
        "<ul>",
    ]
    
    for summary in summaries:
        lines.append(
            f'<li><b>{summary.message}</b>: {summary.count} occurrences</li>'
        )
    
    lines.extend(["</ul>", "</body>", "</html>"])
    
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def load_data(
    entries: List[LogEntry],
    config: Config,
    report_path: Path = Path("report.html"),
) -> None:
    """
    Load processed data to destination (database and HTML report).
    
    Args:
        entries: List of LogEntry objects.
        config: Application configuration.
        report_path: Path to write the HTML report.
    """
    upload_to_database(entries, config)
    summaries = generate_error_summary(entries)
    generate_html_report(summaries, report_path)


# =============================================================================
# ETL Pipeline Orchestration
# =============================================================================

def run_etl_pipeline(config: Config) -> None:
    """
    Execute the complete ETL pipeline.
    
    Args:
        config: Application configuration.
    """
    # Extract
    raw_lines = extract_logs(config)
    
    # Transform
    entries = transform_logs(raw_lines)
    
    # Load
    load_data(entries, config)
    
    print(f"Job finished at {datetime.now()}")


# =============================================================================
# Mock Data Setup
# =============================================================================

def create_mock_log(log_path: Path) -> None:
    """
    Create a mock log file for testing/demo purposes.
    
    Args:
        log_path: Path where the mock log should be created.
    """
    log_content = """\
2024-01-01 12:00:00 INFO User 42 logged in
2024-01-01 12:05:00 ERROR Database timeout
2024-01-01 12:05:05 ERROR Database timeout
2024-01-01 12:10:00 INFO User 42 logged out
"""
    log_path.write_text(log_content, encoding="utf-8")


# =============================================================================
# Main Entry Point
# =============================================================================

def main() -> int:
    """
    Main entry point for the ETL pipeline.
    
    Returns:
        Exit code (0 for success, 1 for failure).
    """
    config = Config.from_env()
    
    # Setup mock data if log file doesn't exist
    if not config.log_file.exists():
        create_mock_log(config.log_file)
    
    try:
        run_etl_pipeline(config)
        return 0
    except Exception as e:
        print(f"ETL pipeline failed: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())