import os
import re
from typing import Dict, List

# Configurable parameters
DB_HOST = "localhost"
DB_USER = "admin"
LOG_FILE = "server.log"
REPORT_FILE = "report.html"


def extract_log_entries(log_file_path: str) -> List[Dict[str, str]]:
    """Extract relevant log entries from file using robust regex parsing."""
    entries = []
    if not os.path.exists(log_file_path):
        return entries

    pattern = r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) (\w+) (.*)$"
    with open(log_file_path, "r") as f:
        for line in f:
            line = line.strip()
            match = re.match(pattern, line)
            if match:
                timestamp, level, message = match.groups()
                if level == "ERROR":
                    entries.append({"date": timestamp, "type": level, "msg": message})
    return entries


def transform_error_data(entries: List[Dict[str, str]]) -> Dict[str, int]:
    """Count occurrences of each unique error message."""
    error_counts = {}
    for entry in entries:
        error_msg = entry["msg"]
        error_counts[error_msg] = error_counts.get(error_msg, 0) + 1
    return error_counts


def load_report(data: Dict[str, int], output_path: str) -> None:
    """Generate HTML report with error statistics."""
    html = "<html><body><h1>Report</h1><ul>"
    for error_msg, count in data.items():
        html += f"<li>{error_msg}: {count}</li>"
    html += "</ul></body></html>"

    with open(output_path, "w") as f:
        f.write(html)


if __name__ == "__main__":
    # Setup test environment
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, "w") as f:
            f.write("2023-10-01 10:00:00 INFO User 123 logged in\n")
            f.write("2023-10-01 10:05:00 ERROR Connection failed\n")
            f.write("2023-10-01 10:10:00 ERROR Connection failed\n")

    # ETL Process
    print(f"Connecting to {DB_HOST} as {DB_USER}...")

    log_entries = extract_log_entries(LOG_FILE)
    error_report = transform_error_data(log_entries)
    load_report(error_report, REPORT_FILE)

    print("Done.")
