import os
import re
from typing import Dict, List

from config import DB_HOST, DB_USER, LOG_FILE, REPORT_FILE


class LogEntry:
    def __init__(self, date: str, log_type: str, message: str, user: str = None):
        self.date = date
        self.log_type = log_type
        self.message = message
        self.user = user


def extract_logs(file_path: str) -> List[LogEntry]:
    entries = []
    log_entry_pattern = re.compile(
        r"(?P<date>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) (?P<type>INFO|ERROR) (?P<message>.+)"
    )
    user_pattern = re.compile(r"User (\d+)")

    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            lines = f.readlines()
            for line in lines:
                match = log_entry_pattern.match(line)
                if match:
                    date = match.group("date")
                    log_type = match.group("type")
                    message = match.group("message").strip()
                    user = None
                    if log_type == "INFO":
                        user_match = user_pattern.search(message)
                        if user_match:
                            user = user_match.group(1)
                    entries.append(LogEntry(date, log_type, message, user))
    return entries


def transform_logs(entries: List[LogEntry]) -> Dict[str, int]:
    report = {}
    for entry in entries:
        if entry.log_type == "ERROR":
            if entry.message not in report:
                report[entry.message] = 0
            report[entry.message] += 1
    return report


def load_report(report: Dict[str, int], report_path: str):
    html = "<html><body><h1>Report</h1><ul>"
    for message, count in report.items():
        html += f"<li>{message}: {count}</li>"
    html += "</ul></body></html>"
    with open(report_path, "w") as f:
        f.write(html)


def etl_process():
    # Extract
    logs = extract_logs(LOG_FILE)

    # Transform
    report = transform_logs(logs)

    # Simulate database connection
    print(f"Connecting to {DB_HOST} as {DB_USER}...")

    # Load
    load_report(report, REPORT_FILE)
    print("Done.")


if __name__ == "__main__":
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, "w") as f:
            f.write("2023-10-01 10:00:00 INFO User 123 logged in\n")
            f.write("2023-10-01 10:05:00 ERROR Connection failed\n")
            f.write("2023-10-01 10:10:00 ERROR Connection failed\n")

    etl_process()
