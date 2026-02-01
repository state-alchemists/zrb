import os
import re
from typing import Dict, Any, Iterator

from config import DB_HOST, DB_USER, LOG_FILE

# Regex patterns
ERROR_PATTERN = re.compile(r"(?P<date>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) ERROR (?P<msg>.*)")
USER_ACTION_PATTERN = re.compile(r"(?P<date>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) INFO User (?P<user_id>\w+) logged in")

def extract_data(log_file_path: str) -> Iterator[Dict[str, Any]]:
    """Extracts data from the log file using regex patterns."""
    if not os.path.exists(log_file_path):
        return

    with open(log_file_path, "r") as f:
        for line in f:
            error_match = ERROR_PATTERN.match(line)
            if error_match:
                yield {"date": error_match.group("date"), "type": "ERROR", "msg": error_match.group("msg").strip()}
                continue

            user_action_match = USER_ACTION_PATTERN.match(line)
            if user_action_match:
                yield {"date": user_action_match.group("date"), "type": "USER_ACTION", "user": user_action_match.group("user_id")}
                continue


def transform_data(extracted_items: Iterator[Dict[str, Any]]) -> Dict[str, int]:
    """Transforms extracted log data into a report of error counts."""
    report: Dict[str, int] = {}
    for item in extracted_items:
        if item["type"] == "ERROR":
            msg = item["msg"]
            report[msg] = report.get(msg, 0) + 1
    return report


def load_report(report_data: Dict[str, int], output_file: str = "report.html") -> None:
    """Loads the transformed data into an HTML report file."""
    # Simulate database connection (from original script)
    print(f"Connecting to {DB_HOST} as {DB_USER}...")

    html_content = "<html><body><h1>Report</h1><ul>"
    for k, v in report_data.items():
        html_content += f"<li>{k}: {v}</li>"
    html_content += "</ul></body></html>"

    with open(output_file, "w") as f:
        f.write(html_content)
    print(f"Report generated: {output_file}")


def main():
    # Create dummy log file if not exists for testing (moved from original __main__)
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, "w") as f:
            f.write("2023-10-01 10:00:00 INFO User 123 logged in\n")
            f.write("2023-10-01 10:05:00 ERROR Connection failed\n")
            f.write("2023-10-01 10:10:00 ERROR Connection failed\n")
            f.write("2023-10-01 10:15:00 INFO User 456 logged in\n")
            f.write("2023-10-01 10:20:00 ERROR Authentication error\n")

    extracted_items = extract_data(LOG_FILE)
    transformed_report = transform_data(extracted_items)
    load_report(transformed_report)
    print("Done.")

if __name__ == "__main__":
    main()