import datetime
import os
import re
from typing import Dict, List, Optional, TypedDict

# --- Configuration ---
# Use environment variables for sensitive or deployment-specific settings
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_USER = os.getenv("DB_USER", "admin")
DB_PASS = os.getenv("DB_PASS", "password123")  # This should ideally be handled more securely
LOG_FILE_PATH = os.getenv("LOG_FILE", "server.log")
REPORT_FILE_PATH = "report.html"

# Regex for parsing log lines:
# It captures:
# 1. Timestamp (e.g., "2024-01-01 12:00:00")
# 2. Log Level (e.g., "INFO", "ERROR")
# 3. Message (the rest of the line)
LOG_PATTERN = re.compile(r"^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s+(?P<level>\w+)\s+(?P<message>.*)$")

# --- Data Structures ---
class LogEntry(TypedDict):
    timestamp: str
    level: str
    message: str
    user_id: Optional[str] # Optional for user_id as it's not always present

class ErrorSummary(TypedDict):
    error_message: str
    count: int

# --- ETL Functions ---

def extract_logs(log_file: str) -> List[str]:
    """
    Extracts raw log lines from the specified log file.
    """
    log_lines: List[str] = []
    if os.path.exists(log_file):
        with open(log_file, "r") as f:
            log_lines = f.readlines()
    return log_lines

def parse_log_line(line: str) -> Optional[LogEntry]:
    """
    Parses a single log line into a structured LogEntry.
    Returns None if the line cannot be parsed.
    """
    match = LOG_PATTERN.match(line.strip())
    if not match:
        return None

    data = match.groupdict()
    timestamp = data["timestamp"]
    level = data["level"]
    message = data["message"].strip()
    user_id: Optional[str] = None

    if level == "INFO" and "User" in message:
        # Extract user ID for INFO messages containing "User"
        user_match = re.search(r"User (\d+) logged (?:in|out)", message)
        if user_match:
            user_id = user_match.group(1)

    return {
        "timestamp": timestamp,
        "level": level,
        "message": message,
        "user_id": user_id,
    }

def transform_data(parsed_logs: List[LogEntry]) -> Dict[str, int]:
    """
    Transforms parsed log entries to aggregate error counts.
    """
    error_counts: Dict[str, int] = {}
    for entry in parsed_logs:
        if entry["level"] == "ERROR":
            error_message = entry["message"].strip()
            error_counts[error_message] = error_counts.get(error_message, 0) + 1
    return error_counts

def generate_report_html(error_summary: Dict[str, int], output_file: str) -> None:
    """
    Generates an HTML report from the error summary and writes it to a file.
    """
    out = "<html>\n<head><title>System Report</title></head>\n<body>\n"
    out += "<h1>Error Summary</h1>\n<ul>\n"
    for err_msg, count in error_summary.items():
        out += f"<li><b>{err_msg}</b>: {count} occurrences</li>\n"
    out += "</ul>\\n</body>\\n</html>"
    with open(output_file, "w") as f:
        f.write(out)
    print(f"Report generated at {output_file}")

# --- Main ETL Process ---

def run_etl() -> None:
    """
    Orchestrates the entire ETL process: Extract, Transform, Load.
    """
    # Simulate DB connection (as per original script)
    print(f"Connecting to {DB_HOST} as {DB_USER}...")
    # NOTE: Actual database insertion logic would go here.

    # 1. Extract
    print(f"Extracting logs from {LOG_FILE_PATH}...")
    raw_log_lines = extract_logs(LOG_FILE_PATH)

    # 2. Transform
    print("Parsing and transforming log data...")
    parsed_logs: List[LogEntry] = []
    for line in raw_log_lines:
        parsed_entry = parse_log_line(line)
        if parsed_entry:
            parsed_logs.append(parsed_entry)

    error_summary = transform_data(parsed_logs)

    # 3. Load
    print(f"Generating HTML report to {REPORT_FILE_PATH}...")
    generate_report_html(error_summary, REPORT_FILE_PATH)

    print(f"ETL Job finished at {datetime.datetime.now()}")

# --- Entry Point ---

if __name__ == "__main__":
    # Setup dummy data if needed, matching the original script's behavior
    if not os.path.exists(LOG_FILE_PATH):
        print(f"'{LOG_FILE_PATH}' not found. Creating dummy log data.")
        with open(LOG_FILE_PATH, "w") as f:
            f.write("2024-01-01 12:00:00 INFO User 42 logged in\n")
            f.write("2024-01-01 12:05:00 ERROR Database timeout\n")
            f.write("2024-01-01 12:05:05 ERROR Database timeout\n")
            f.write("2024-01-01 12:10:00 INFO User 42 logged out\n")
            f.write("2024-01-01 12:15:00 INFO    User    55   logged in  \n") # Test for extra spaces
            f.write("2024-01-01 12:20:00 ERROR Another error message with spaces \n") # Test for extra spaces

    run_etl()
