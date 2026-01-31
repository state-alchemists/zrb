import os
import re
from typing import Dict, List

from config import DB_HOST, DB_USER, LOG_FILE


def extract_log_data(log_file: str) -> List[Dict[str, str]]:
    data = []
    log_pattern = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) (\w+) (.+)$")
    with open(log_file, "r") as f:
        for line in f:
            match = log_pattern.match(line)
            if match:
                date, log_type, message = match.groups()
                if log_type == "ERROR":
                    data.append(
                        {"date": date, "type": log_type, "msg": message.strip()}
                    )
                elif log_type == "INFO" and "User" in message:
                    user_id_search = re.search(r"User (\d+)", message)
                    if user_id_search:
                        user_id = user_id_search.group(1)
                        data.append(
                            {"date": date, "type": "USER_ACTION", "user": user_id}
                        )
    return data


def transform_data(data: List[Dict[str, str]]) -> Dict[str, int]:
    report = {}
    for item in data:
        if item["type"] == "ERROR":
            if item["msg"] not in report:
                report[item["msg"]] = 0
            report[item["msg"]] += 1
    return report


def load_report(report: Dict[str, int], output_file: str):
    html = "<html><body><h1>Report</h1><ul>"
    for k, v in report.items():
        html += f"<li>{k}: {v}</li>"
    html += "</ul></body></html>"
    with open(output_file, "w") as f:
        f.write(html)


def main():
    print(f"Connecting to {DB_HOST} as {DB_USER}...")
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, "w") as f:
            f.write("2023-10-01 10:00:00 INFO User 123 logged in\n")
            f.write("2023-10-01 10:05:00 ERROR Connection failed\n")
            f.write("2023-10-01 10:10:00 ERROR Connection failed\n")
    data = extract_log_data(LOG_FILE)
    report = transform_data(data)
    load_report(report, "report.html")
    print("Done.")


if __name__ == "__main__":
    main()
