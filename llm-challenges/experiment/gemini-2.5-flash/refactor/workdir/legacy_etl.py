import datetime
import os
import re
import sys
from typing import Any, Dict, List


class Config:
    """
    Configuration class to hold application settings.
    Uses environment variables or sensible defaults.
    """

    def __init__(self):
        self.db_host: str = os.getenv("DB_HOST", "localhost")
        self.db_user: str = os.getenv("DB_USER", "admin")
        self.log_file: str = os.getenv("LOG_FILE", "server.log")
        self.report_file: str = os.getenv("REPORT_FILE", "report.html")


def setup_dummy_log_file(log_file_path: str) -> None:
    """
    Creates a dummy log file for testing purposes if it doesn't already exist.
    """
    if not os.path.exists(log_file_path):
        with open(log_file_path, "w") as f:
            f.write("2023-10-01 10:00:00 INFO User 123 logged in\\n")
            f.write("2023-10-01 10:05:00 ERROR Connection failed\\n")
            f.write("2023-10-01 10:10:00 ERROR Connection failed\\n")
            f.write("2023-10-01 10:15:00 INFO User 456 logged out\\n")
            f.write("2023-10-01 10:20:00 ERROR Database timeout\\n")
        print(f"Dummy log file created at {log_file_path}")


def extract_log_data(log_file_path: str) -> List[Dict[str, Any]]:
    """
    Extracts structured data from a log file.
    Parses log entries using regex to identify timestamps, types, messages, and user IDs.

    Args:
        log_file_path: The path to the log file.

    Returns:
        A list of dictionaries, each representing a parsed log entry.
    """
    data: List[Dict[str, Any]] = []
    if not os.path.exists(log_file_path):
        print(f"Log file not found: {log_file_path}", file=sys.stderr)
        return data

    # Regex to match log lines: YYYY-MM-DD HH:MM:SS (INFO|ERROR) Message...
    # Also tries to capture User IDs if present in INFO messages.
    log_pattern = re.compile(
        r"^(?P<date>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) "
        r"(?P<type>INFO|ERROR) "
        r"(?:User (?P<user_id>\d+) )?"  # Optional user ID for INFO messages
        r"(?P<message>.*)$"
    )

    with open(log_file_path, "r") as f:
        for line in f:
            match = log_pattern.match(line.strip())
            if match:
                log_entry = match.groupdict()
                processed_entry: Dict[str, Any] = {
                    "date": log_entry["date"],
                    "type": log_entry["type"],
                    "msg": log_entry["message"].strip(),
                }
                if log_entry["type"] == "INFO" and log_entry["user_id"]:
                    processed_entry["type"] = "USER_ACTION"
                    processed_entry["user"] = log_entry["user_id"]
                    # Remove "User ID logged in/out" from msg for user actions
                    processed_entry["msg"] = re.sub(
                        r"User \d+ (logged in|logged out)", "", processed_entry["msg"]
                    ).strip()
                data.append(processed_entry)
            else:
                print(f"Could not parse log line: {line.strip()}", file=sys.stderr)
    return data


def transform_data(extracted_data: List[Dict[str, Any]]) -> Dict[str, int]:
    """
    Transforms extracted log data into a report, e.g., counting error messages.

    Args:
        extracted_data: A list of dictionaries from the extract phase.

    Returns:
        A dictionary where keys are error messages and values are their counts.
    """
    report: Dict[str, int] = {}
    for item in extracted_data:
        if item["type"] == "ERROR":
            if item["msg"] not in report:
                report[item["msg"]] = 0
            report[item["msg"]] += 1
    return report


def generate_html_report(report_data: Dict[str, int], output_file_path: str) -> None:
    """
    Generates an HTML report from the transformed data.

    Args:
        report_data: A dictionary containing the aggregated report (e.g., error counts).
        output_file_path: The path where the HTML report will be saved.
    """
    html = """<html>
<head>
    <title>ETL Report</title>
    <style>
        body { font-family: sans-serif; margin: 20px; }
        h1 { color: #333; }
        ul { list-style-type: none; padding: 0; }
        li { background-color: #f4f4f4; margin-bottom: 5px; padding: 10px; border-radius: 5px; }
    </style>
</head>
<body>
    <h1>ETL Report</h1>
    <h2>Error Summary</h2>
    <ul>
"""
    for k, v in report_data.items():
        html += f"        <li><strong>{k}</strong>: {v} times</li>\\n"
    html += """    </ul>
</body>
</html>"""

    with open(output_file_path, "w") as f:
        f.write(html)
    print(f"HTML report generated at {output_file_path}")


def main():
    """
    Main function to orchestrate the ETL process.
    Initializes configuration, sets up dummy data, extracts, transforms, and loads.
    """
    config = Config()
    print(f"Connecting to database at {config.db_host} as user {config.db_user}...")

    # Ensure dummy log file exists for demonstration
    setup_dummy_log_file(config.log_file)

    # 1. Extract
    extracted_data = extract_log_data(config.log_file)
    print(f"Extracted {len(extracted_data)} log entries.")

    # 2. Transform
    transformed_report = transform_data(extracted_data)
    print(
        f"Transformed data into a report with {len(transformed_report)} unique error types."
    )

    # 3. Load/Report
    generate_html_report(transformed_report, config.report_file)
    print("ETL process completed successfully.")


if __name__ == "__main__":
    main()
