import os
import re
from typing import Any, Dict, Iterator

from config import DB_HOST, DB_USER, LOG_FILE


def extract_data(log_file: str) -> Iterator[str]:
    """Extracts raw log lines from the log file."""
    if os.path.exists(log_file):
        with open(log_file, "r") as f:
            for line in f:
                yield line.strip()


def transform_data(log_lines: Iterator[str]) -> Iterator[Dict[str, Any]]:
    """Transforms raw log lines into structured data using regex."""
    log_pattern = re.compile(
        r"^(?P<date>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) "
        r"(?P<level>INFO|ERROR) "
        r"(?P<message>.*)$"
    )
    user_action_pattern = re.compile(r".*User (?P<user_id>\d+) logged in.*")

    for line in log_lines:
        match = log_pattern.match(line)
        if match:
            data = match.groupdict()
            if data["level"] == "ERROR":
                yield {"date": data["date"], "type": "ERROR", "msg": data["message"]}
            elif data["level"] == "INFO":
                user_match = user_action_pattern.match(data["message"])
                if user_match:
                    yield {
                        "date": data["date"],
                        "type": "USER_ACTION",
                        "user": user_match.groupdict()["user_id"],
                    }


def load_data(structured_data: Iterator[Dict[str, Any]]) -> None:
    """Aggregates data and generates the report.html file."""
    print(f"Connecting to {DB_HOST} as {DB_USER}...")

    report: Dict[str, int] = {}
    for item in structured_data:
        if item["type"] == "ERROR":
            report.setdefault(item["msg"], 0)
            report[item["msg"]] += 1

    html = "<html><body><h1>Report</h1><ul>"
    for k, v in report.items():
        html += f"<li>{k}: {v}</li>"
    html += "</ul></body></html>"

    with open("report.html", "w") as f:
        f.write(html)
    print("Done.")


def main():
    """Orchestrates the ETL process."""
    # Create dummy log file if not exists for testing
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, "w") as f:
            f.write("2023-10-01 10:00:00 INFO User 123 logged in\n")
            f.write("2023-10-01 10:05:00 ERROR Connection failed\n")
            f.write("2023-10-01 10:10:00 ERROR Connection failed\n")

    log_lines = extract_data(LOG_FILE)
    structured_data = transform_data(log_lines)
    load_data(structured_data)


if __name__ == "__main__":
    main()
