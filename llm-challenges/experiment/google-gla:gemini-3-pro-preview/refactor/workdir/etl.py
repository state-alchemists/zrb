import os
import re
from dataclasses import dataclass
from typing import Dict, List, NamedTuple, Optional


# --- Configuration ---
@dataclass
class Config:
    DB_HOST: str = "localhost"
    DB_USER: str = "admin"
    LOG_FILE: str = "server.log"
    REPORT_FILE: str = "report.html"


# --- Data Structures ---
class LogEntry(NamedTuple):
    timestamp: str
    level: str
    message: str


class ParsedData(NamedTuple):
    errors: List[LogEntry]
    user_actions: List[Dict[str, str]]


# --- ETL Stages ---


def extract(file_path: str) -> List[str]:
    """Reads raw lines from the log file."""
    if not os.path.exists(file_path):
        return []
    with open(file_path, "r") as f:
        return f.readlines()


def transform(lines: List[str]) -> ParsedData:
    """Parses log lines and aggregates data."""
    # Regex for parsing the log line: Date Time Level Message
    # Example: 2023-10-01 10:05:00 ERROR Connection failed
    log_pattern = re.compile(
        r"^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s+(?P<level>\w+)\s+(?P<message>.*)$"
    )

    errors: List[LogEntry] = []
    user_actions: List[Dict[str, str]] = []

    for line in lines:
        line = line.strip()
        if not line:
            continue

        match = log_pattern.match(line)
        if match:
            timestamp = match.group("timestamp")
            level = match.group("level")
            message = match.group("message")

            if level == "ERROR":
                errors.append(LogEntry(timestamp, level, message))
            elif level == "INFO":
                # Logic from original script: extract user ID if "User" is in message
                # Original logic: user_id = msg.split("User")[1].split(" ")[1]
                # Msg: "User 123 logged in" -> split("User")[1] is " 123 logged in" -> split(" ")[1] is "123"
                if "User" in message:
                    # Using regex for robust extraction of user id
                    user_match = re.search(r"User\s+(\S+)", message)
                    if user_match:
                        user_id = user_match.group(1)
                        user_actions.append(
                            {"date": timestamp, "type": "USER_ACTION", "user": user_id}
                        )

    return ParsedData(errors=errors, user_actions=user_actions)


def load(data: ParsedData, config: Config) -> None:
    """Simulates DB load and generates HTML report."""
    # Simulate database connection
    print(f"Connecting to {config.DB_HOST} as {config.DB_USER}...")

    # In a real app, we might insert data here.
    # The original script didn't actually insert, just printed.

    # Generate Report Aggregation
    report_counts: Dict[str, int] = {}
    for error in data.errors:
        msg = error.message
        if msg not in report_counts:
            report_counts[msg] = 0
        report_counts[msg] += 1

    # Generate HTML
    html_content = "<html><body><h1>Report</h1><ul>"
    for msg, count in report_counts.items():
        html_content += f"<li>{msg}: {count}</li>"
    html_content += "</ul></body></html>"

    with open(config.REPORT_FILE, "w") as f:
        f.write(html_content)


def main():
    config = Config()

    # Ensure dummy file exists (preserving original test logic)
    if not os.path.exists(config.LOG_FILE):
        with open(config.LOG_FILE, "w") as f:
            f.write("2023-10-01 10:00:00 INFO User 123 logged in\n")
            f.write("2023-10-01 10:05:00 ERROR Connection failed\n")
            f.write("2023-10-01 10:10:00 ERROR Connection failed\n")

    # ETL Pipeline
    raw_lines = extract(config.LOG_FILE)
    transformed_data = transform(raw_lines)
    load(transformed_data, config)

    print("Done.")


if __name__ == "__main__":
    main()
