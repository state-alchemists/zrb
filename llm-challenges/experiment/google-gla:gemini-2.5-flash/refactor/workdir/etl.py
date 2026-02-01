import os
import re
from typing import Any, Dict, Iterator, List

from config import DB_HOST, DB_USER, LOG_ENTRY_REGEX, LOG_FILE, USER_ACTION_REGEX


def extract_logs(log_file: str) -> Iterator[str]:
    """Extracts raw log entries from the log file."""
    if not os.path.exists(log_file):
        return
    with open(log_file, "r") as f:
        for line in f:
            yield line.strip()


def parse_log_entry(raw_entry: str) -> Dict[str, Any] | None:
    """Parses a raw log entry using regex and extracts relevant information."""
    match = LOG_ENTRY_REGEX.match(raw_entry)
    if not match:
        return None

    data: Dict[str, Any] = match.groupdict()
    data["timestamp"] = data.pop("date")  # Rename 'date' to 'timestamp'

    if data["level"] == "INFO" and "User" in data["message"]:
        user_match = USER_ACTION_REGEX.match(data["message"])
        if user_match:
            data["type"] = "USER_ACTION"
            data["user_id"] = int(user_match.group("user_id"))
        else:
            data["type"] = "INFO"
    elif data["level"] == "ERROR":
        data["type"] = "ERROR"
    else:
        data["type"] = data["level"]

    return data


def transform_data(parsed_entries: List[Dict[str, Any]]) -> Dict[str, int]:
    """Transforms parsed log entries into a report, counting error messages."""
    report: Dict[str, int] = {}
    for item in parsed_entries:
        if item["type"] == "ERROR":
            msg = item["message"]
            if msg not in report:
                report[msg] = 0
            report[msg] += 1
    return report


def generate_report_html(report_data: Dict[str, int]) -> str:
    """Generates an HTML report from the transformed data."""
    html = "<html><body><h1>Report</h1><ul>"
    for k, v in report_data.items():
        html += f"<li>{k}: {v}</li>"
    html += "</ul></body></html>"
    return html


def load_report(html_content: str, output_file: str) -> None:
    """Writes the HTML content to the specified output file."""
    with open(output_file, "w") as f:
        f.write(html_content)
    print(f"Report written to {output_file}")


def main():
    # Simulate database connection
    print(f"Connecting to {DB_HOST} as {DB_USER}...")

    # ETL Process
    raw_log_entries = list(extract_logs(LOG_FILE))
    parsed_entries: List[Dict[str, Any]] = []
    for entry in raw_log_entries:
        parsed = parse_log_entry(entry)
        if parsed:
            parsed_entries.append(parsed)

    report_data = transform_data(parsed_entries)
    html_report = generate_report_html(report_data)
    load_report(html_report, "report.html")

    print("Done.")


if __name__ == "__main__":
    # Create dummy log file if not exists for testing
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, "w") as f:
            f.write("2023-10-01 10:00:00 INFO User 123 logged in\n")
            f.write("2023-10-01 10:05:00 ERROR Connection failed\n")
            f.write("2023-10-01 10:10:00 ERROR Connection failed\n")

    main()
