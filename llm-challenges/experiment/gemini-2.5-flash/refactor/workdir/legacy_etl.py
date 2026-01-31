import os
import re
from typing import Any, Dict, List

from config import DB_HOST, DB_USER, LOG_FILE


def extract_data(log_file: str) -> List[Dict[str, str]]:
    """
    Extracts raw log data from the specified log file.
    """
    data: List[Dict[str, str]] = []
    if os.path.exists(log_file):
        with open(log_file, "r") as f:
            for line in f:
                data.append({"raw_line": line.strip()})
    return data


def transform_data(raw_data: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    """
    Transforms raw log lines into structured events using regex.
    """
    transformed_events: List[Dict[str, Any]] = []
    error_pattern = re.compile(
        r"^(?P<date>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) ERROR (?P<message>.*)$"
    )
    info_user_pattern = re.compile(
        r"^(?P<date>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) INFO User (?P<user_id>\d+) logged in$"
    )

    for item in raw_data:
        line = item["raw_line"]
        error_match = error_pattern.match(line)
        info_user_match = info_user_pattern.match(line)

        if error_match:
            transformed_events.append(
                {
                    "date": error_match.group("date"),
                    "type": "ERROR",
                    "msg": error_match.group("message").strip(),
                }
            )
        elif info_user_match:
            transformed_events.append(
                {
                    "date": info_user_match.group("date"),
                    "type": "USER_ACTION",
                    "user": info_user_match.group("user_id"),
                }
            )
    return transformed_events


def load_data(events: List[Dict[str, Any]], db_host: str, db_user: str) -> None:
    """
    Loads transformed data, simulating a database connection and generating an HTML report.
    """
    print(f"Connecting to {db_host} as {db_user}...")

    error_report: Dict[str, int] = {}
    for event in events:
        if event["type"] == "ERROR":
            msg = event["msg"]
            error_report[msg] = error_report.get(msg, 0) + 1

    html_content = "<html><body><h1>Report</h1><ul>"
    for k, v in error_report.items():
        html_content += f"<li>{k}: {v}</li>"
    html_content += "</ul></body></html>"

    with open("report.html", "w") as f:
        f.write(html_content)

    print("Done.")


def main():
    # Create dummy log file if not exists for testing
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, "w") as f:
            f.write("2023-10-01 10:00:00 INFO User 123 logged in\n")
            f.write("2023-10-01 10:05:00 ERROR Connection failed\n")
            f.write("2023-10-01 10:10:00 ERROR Connection failed\n")

    raw_data = extract_data(LOG_FILE)
    transformed_events = transform_data(raw_data)
    load_data(transformed_events, DB_HOST, DB_USER)


if __name__ == "__main__":
    main()
