import datetime
import os
import re
from typing import Any, Dict, List, Optional


# Configuration Class
class Config:
    LOG_FILE: str = "server.log"
    REPORT_FILE: str = "report.html"
    DB_HOST: str = "localhost"
    DB_USER: str = "admin"


# Data Structures
LogEntry = Dict[str, Any]
ReportData = Dict[str, int]


# --- Extract ---
def extract_logs(log_file: str) -> List[str]:
    """
    Extracts raw log lines from the specified log file.
    """
    if not os.path.exists(log_file):
        print(f"Log file not found: {log_file}")
        return []
    with open(log_file, "r") as f:
        return f.readlines()


# --- Transform ---
def parse_log_line(line: str) -> Optional[LogEntry]:
    """
    Parses a single log line using regex and returns a structured dictionary.
    """
    stripped_line = line.strip()
    # Regex to capture date, time, log_type, and message.
    # It also handles optional user ID for INFO messages.
    # Example: "2023-10-01 10:00:00 INFO User 123 logged in"
    # Example: "2023-10-01 10:05:00 ERROR Connection failed"
    match = re.match(
        r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) (INFO|ERROR) (.+)$", stripped_line
    )
    if not match:
        return None

    date_str, log_type, message = match.groups()
    entry: LogEntry = {"date": date_str, "type": log_type}

    if log_type == "ERROR":
        entry["msg"] = message.strip()
    elif log_type == "INFO":
        user_match = re.search(r"User (\d+)", message)
        if user_match:
            entry["type"] = "USER_ACTION"
            entry["user"] = user_match.group(1)
            entry["msg"] = message.strip()
        else:
            entry["msg"] = message.strip()  # Store info message if not a user action

    return entry


def transform_data(raw_logs: List[str]) -> ReportData:
    """
    Transforms raw log lines into a reportable data structure.
    """
    parsed_data: List[LogEntry] = []
    for line in raw_logs:
        entry = parse_log_line(line)
        if entry:
            parsed_data.append(entry)

    report: ReportData = {}
    for item in parsed_data:
        if item["type"] == "ERROR":
            error_msg = item.get("msg", "Unknown Error")
            report[error_msg] = report.get(error_msg, 0) + 1
        elif item["type"] == "USER_ACTION":
            # For user actions, we might count unique users or track activity,
            # but for now, we'll stick to the original script's output (only error counts)
            pass

    return report


# --- Load ---
def generate_report_html(report_data: ReportData) -> str:
    """
    Generates the HTML content for the report.
    """
    html = "<html><body><h1>Report</h1><ul>"
    for k, v in report_data.items():
        html += f"<li>{k}: {v}</li>"
    html += "</ul></body></html>"
    return html


def load_report(html_content: str, report_file: str):
    """
    Writes the HTML content to the specified report file.
    """
    with open(report_file, "w") as f:
        f.write(html_content)
    print(f"Report generated: {report_file}")


def simulate_db_connection(config: Config):
    """
    Simulates a database connection.
    """
    print(f"Connecting to {config.DB_HOST} as {config.DB_USER}...")


def main():
    config = Config()

    # Always create dummy log file for testing
    with open(config.LOG_FILE, "w") as f:
        log_content = (
            "2023-10-01 10:00:00 INFO User 123 logged in\n"
            "2023-10-01 10:05:00 ERROR Connection failed\n"
            "2023-10-01 10:10:00 ERROR Connection failed\n"
            "2023-10-01 10:15:00 INFO Another info message\n"
            "2023-10-01 10:20:00 ERROR Database connection timed out\n"
        )
        f.write(log_content)

    print("Starting ETL process...")

    # Extract
    raw_logs = extract_logs(config.LOG_FILE)

    # Simulate DB connection (as it was in the original script before transformation)
    simulate_db_connection(config)

    # Transform
    report_data = transform_data(raw_logs)

    # Load
    html_content = generate_report_html(report_data)
    load_report(html_content, config.REPORT_FILE)

    print("ETL process finished.")


if __name__ == "__main__":
    main()
