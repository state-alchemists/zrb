import datetime
import os
import re
from typing import List, Dict, Any

def get_config() -> Dict[str, str]:
    """
    Retrieves configuration from environment variables.
    """
    return {
        "DB_HOST": os.getenv("DB_HOST", "localhost"),
        "DB_USER": os.getenv("DB_USER", "admin"),
        "LOG_FILE": os.getenv("LOG_FILE", "server.log"),
        "REPORT_FILE": os.getenv("REPORT_FILE", "report.html"),
    }

def extract_log_data(log_file_path: str) -> List[Dict[str, str]]:
    """
    Extracts relevant data from the log file.
    Improved log parsing using regex.
    """
    data: List[Dict[str, str]] = []
    if not os.path.exists(log_file_path):
        print(f"Log file not found: {log_file_path}")
        return data

    log_pattern = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) (INFO|ERROR) (.*)$")

    with open(log_file_path, "r") as f:
        for line in f:
            match = log_pattern.match(line)
            if match:
                timestamp, level, message = match.groups()
                if level == "ERROR":
                    data.append({"date": timestamp, "type": "ERROR", "msg": message.strip()})
                elif level == "INFO":
                    if "User" in message:
                        user_match = re.search(r"User (\\w+) logged in", message)
                        if user_match:
                            user_id = user_match.group(1)
                            data.append({"date": timestamp, "type": "USER_ACTION", "user": user_id})
    return data

def transform_data(extracted_data: List[Dict[str, str]]) -> Dict[str, int]:
    """
    Transforms the extracted data into a report format.
    """
    report: Dict[str, int] = {}
    for item in extracted_data:
        if item["type"] == "ERROR":
            error_msg = item["msg"]
            report[error_msg] = report.get(error_msg, 0) + 1
    return report

def load_report(report_data: Dict[str, int], report_file_path: str) -> None:
    """
    Loads the transformed data into an HTML report file.
    """
    html = "<html><body><h1>Report</h1><ul>"
    for k, v in report_data.items():
        html += f"<li>{k}: {v}</li>"
    html += "</ul></body></html>"

    with open(report_file_path, "w") as f:
        f.write(html)
    print(f"Report generated: {report_file_path}")

def setup_dummy_log_file(log_file_path: str) -> None:
    """
    Creates a dummy log file for testing purposes if it doesn't exist.
    """
    if not os.path.exists(log_file_path):
        with open(log_file_path, "w") as f:
            f.write("2023-10-01 10:00:00 INFO User 123 logged in\n")
            f.write("2023-10-01 10:05:00 ERROR Connection failed\n")
            f.write("2023-10-01 10:10:00 ERROR Connection failed\n")
            f.write("2023-10-01 10:15:00 INFO User 456 logged out\n")
            f.write("2023-10-01 10:20:00 ERROR Disk full\n")
        print(f"Dummy log file created: {log_file_path}")

def main():
    """
    Main function to run the ETL process.
    """
    config = get_config()
    log_file = config["LOG_FILE"]
    report_file = config["REPORT_FILE"]
    db_host = config["DB_HOST"]
    db_user = config["DB_USER"]

    print(f"Connecting to {db_host} as {db_user}...")

    # Setup dummy data if needed
    setup_dummy_log_file(log_file)

    # ETL Process
    extracted_data = extract_log_data(log_file)
    transformed_report = transform_data(extracted_data)
    load_report(transformed_report, report_file)

    print("ETL process completed.")

if __name__ == "__main__":
    main()
