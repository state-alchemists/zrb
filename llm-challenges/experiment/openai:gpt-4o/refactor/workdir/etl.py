import datetime
import os
import re
from typing import Any, Dict, List

# Import configuration
from config import DB_HOST, DB_USER, LOG_FILE


def extract(log_file: str) -> List[Dict[str, Any]]:
    data = []
    log_pattern = re.compile(
        r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) (ERROR|INFO) (.*)$"
    )
    if os.path.exists(log_file):
        with open(log_file, "r") as f:
            for line in f:
                match = log_pattern.match(line)
                if match:
                    date_str, log_type, message = match.groups()
                    if log_type == "ERROR":
                        data.append(
                            {"date": date_str, "type": log_type, "msg": message.strip()}
                        )
                    elif log_type == "INFO" and "User" in message:
                        user_id_search = re.search(r"User (\d+)", message)
                        if user_id_search:
                            user_id = user_id_search.group(1)
                            data.append(
                                {
                                    "date": date_str,
                                    "type": "USER_ACTION",
                                    "user": user_id,
                                }
                            )
    return data


def transform(data: List[Dict[str, Any]]) -> Dict[str, int]:
    report = {}
    for item in data:
        if item["type"] == "ERROR":
            if item["msg"] not in report:
                report[item["msg"]] = 0
            report[item["msg"]] += 1
    return report


def load(report: Dict[str, int], output_file: str) -> None:
    html_content = "<html><body><h1>Report</h1><ul>"
    for error_msg, count in report.items():
        html_content += f"<li>{error_msg}: {count}</li>"
    html_content += "</ul></body></html>"
    with open(output_file, "w") as f:
        f.write(html_content)


def main() -> None:
    data = extract(LOG_FILE)
    report = transform(data)
    load(report, "report.html")
    print(f"Connecting to {DB_HOST} as {DB_USER}...")
    print("Done.")


if __name__ == "__main__":
    # Create dummy log file if not exists for testing
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, "w") as f:
            f.write("2023-10-01 10:00:00 INFO User 123 logged in\n")
            f.write("2023-10-01 10:05:00 ERROR Connection failed\n")
            f.write("2023-10-01 10:10:00 ERROR Connection failed\n")

    main()
