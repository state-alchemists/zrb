"""ETL (Extract, Transform, Load) process for log analysis.

This module implements a clean ETL pipeline that:
- Extracts data from log files
- Transforms log entries into summary statistics
- Loads/manages the HTML report output
"""

import html
import sys
from collections import Counter
from pathlib import Path

from config import config
from parser import LogEntry, parse_log_file


def extract_logs(filepath: str | Path | None = None) -> list[LogEntry]:
    """Extract log entries from file.
    
    Args:
        filepath: Path to log file. Uses config.LOG_FILE if None.
        
    Returns:
        List of parsed log entries.
    """
    path = filepath or config.LOG_FILE
    return parse_log_file(path)


def transform_logs(entries: list[LogEntry]) -> dict[str, int]:
    """Transform log entries into error summary statistics.
    
    Args:
        entries: List of parsed log entries.
        
    Returns:
        Dictionary mapping error messages to occurrence counts.
    """
    error_messages: list[str] = []
    
    for entry in entries:
        if entry.level == "ERROR":
            error_messages.append(entry.message)
    
    # Count occurrences of each error message
    return dict(Counter(error_messages))


def load_report(errors: dict[str, int], output_path: str | Path | None = None) -> str:
    """Generate and save the HTML report.
    
    Args:
        errors: Dictionary of error messages to counts.
        output_path: Path for output HTML. Uses config.REPORT_FILE if None.
        
    Returns:
        The generated HTML content as a string.
    """
    # Build HTML with proper escaping to prevent XSS
    lines: list[str] = [
        "<html>",
        "<head><title>System Report</title></head>",
        "<body>",
        "<h1>Error Summary</h1>",
        "<ul>",
    ]
    
    for error_msg, count in sorted(errors.items()):
        # Escape HTML special characters in error messages
        safe_msg = html.escape(error_msg)
        lines.append(f"<li><b>{safe_msg}</b>: {count} occurrences</li>")
    
    lines.extend(["</ul>", "</body>", "</html>"])
    
    html_content = "\n".join(lines)
    
    # Write report file
    path = output_path or config.REPORT_FILE
    with open(path, "w", encoding="utf-8") as f:
        f.write(html_content)
    
    return html_content


def run_etl(
    log_path: str | Path | None = None,
    output_path: str | Path | None = None
) -> dict[str, int]:
    """Run the complete ETL pipeline.
    
    Args:
        log_path: Path to input log file. Uses config.LOG_FILE if None.
        output_path: Path for output HTML report. Uses config.REPORT_FILE if None.
        
    Returns:
        Dictionary of error messages to counts.
    """
    print(f"Connecting to {config.DB_HOST} as {config.DB_USER}...")
    
    # Extract: Read log file
    entries = extract_logs(log_path)
    print(f"Extracted {len(entries)} log entries")
    
    # Transform: Aggregate errors
    error_counts = transform_logs(entries)
    print(f"Transformed into {len(error_counts)} unique error types")
    
    # Load: Generate report
    load_report(error_counts, output_path)
    print(f"Report written to {output_path or config.REPORT_FILE}")
    
    return error_counts


if __name__ == "__main__":
    import datetime
    
    # Create sample log file if it doesn't exist
    log_path = Path(config.LOG_FILE)
    if not log_path.exists():
        log_path.write_text(
            "2024-01-01 12:00:00 INFO User 42 logged in\n"
            "2024-01-01 12:05:00 ERROR Database timeout\n"
            "2024-01-01 12:05:05 ERROR Database timeout\n"
            "2024-01-01 12:10:00 INFO User 42 logged out\n"
        )
        print(f"Created sample log file at {log_path}")
    
    # Run ETL
    errors = run_etl()
    print(f"Job finished at {datetime.datetime.now()}")
    print(f"Found {sum(errors.values())} total errors")
