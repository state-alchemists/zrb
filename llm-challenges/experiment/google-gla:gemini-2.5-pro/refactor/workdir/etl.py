"""
Refactored ETL script.
"""

import datetime
import re
from typing import Dict, Iterator, List, Optional, TypedDict


# 1. Configuration separated from the logic
class Config(TypedDict):
    db_host: str
    db_user: str
    log_file: str
    report_file: str


CONFIG: Config = {
    "db_host": "localhost",
    "db_user": "admin",
    "log_file": "server.log",
    "report_file": "report.html",
}


# Define data structures with type hints
class LogEntry(TypedDict):
    date: datetime.datetime
    type: str
    msg: str


class UserAction(TypedDict):
    date: datetime.datetime
    type: str
    user: str


TransformedData = List[Dict]

# Regex for parsing log lines
LOG_PATTERN = re.compile(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) (INFO|ERROR) (.*)")
USER_ACTION_PATTERN = re.compile(r"User (\d+)")


def extract_data(log_file: str) -> Iterator[str]:
    """Extracts data from the log file line by line."""
    if not os.path.exists(log_file):
        return
    with open(log_file, "r") as f:
        for line in f:
            yield line.strip()


def transform_data(lines: Iterator[str]) -> TransformedData:
    """Transforms raw log lines into structured data."""
    data: TransformedData = []
    for line in lines:
        match = LOG_PATTERN.match(line)
        if not match:
            continue

        date_str, log_type, msg = match.groups()
        date = datetime.datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")

        if log_type == "ERROR":
            data.append({"date": date, "type": "ERROR", "msg": msg})
        elif log_type == "INFO":
            user_match = USER_ACTION_PATTERN.search(msg)
            if user_match:
                user_id = user_match.group(1)
                data.append({"date": date, "type": "USER_ACTION", "user": user_id})
    return data


def load_report(data: TransformedData, report_file: str):
    """Loads the transformed data into an HTML report."""
    print(f"Connecting to {CONFIG['db_host']} as {CONFIG['db_user']}...")

    report: Dict[str, int] = {}
    for item in data:
        if item.get("type") == "ERROR":
            msg = item.get("msg", "Unknown Error")
            report[msg] = report.get(msg, 0) + 1

    html = "<html><body><h1>Report</h1><ul>"
    for k, v in report.items():
        html += f"<li>{k}: {v}</li>"
    html += "</ul></body></html>"

    with open(report_file, "w") as f:
        f.write(html)


def main():
    """Main function to run the ETL process."""
    # Create dummy log file if not exists for testing
    if not os.path.exists(CONFIG["log_file"]):
        with open(CONFIG["log_file"], "w") as f:
            f.write("2023-10-01 10:00:00 INFO User 123 logged in\n")
            f.write("2023-10-01 10:05:00 ERROR Connection failed\n")
            f.write("2023-10-01 10:10:00 ERROR Connection failed\n")

    lines = extract_data(CONFIG["log_file"])
    transformed_data = transform_data(lines)
    load_report(transformed_data, CONFIG["report_file"])
    print("Done.")


if __name__ == "__main__":
    import os

    main()
