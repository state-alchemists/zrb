import os
import re
from typing import Any, Dict, List

# Config
CONFIG = {
    "DB_HOST": "localhost",
    "DB_USER": "admin",
    "LOG_FILE": "server.log",
    "REPORT_FILE": "report.html",
}


def extract_log_entries(log_file: str) -> List[Dict[str, Any]]:
    data = []
    if os.path.exists(log_file):
        with open(log_file, "r") as f:
            lines = f.readlines()
            for line in lines:
                error_match = re.match(r"^(\S+ \S+) ERROR (.+)$", line)
                info_match = re.match(r"^(\S+ \S+) INFO User (\d+)", line)
                if error_match:
                    date, msg = error_match.groups()
                    data.append({"date": date, "type": "ERROR", "msg": msg.strip()})
                elif info_match:
                    date, user_id = info_match.groups()
                    data.append({"date": date, "type": "USER_ACTION", "user": user_id})
    return data


def transform_data(data: List[Dict[str, Any]]) -> Dict[str, int]:
    report = {}
    for item in data:
        if item["type"] == "ERROR":
            report[item["msg"]] = report.get(item["msg"], 0) + 1
    return report


def load_report(report: Dict[str, int], report_file: str) -> None:
    html = "<html><body><h1>Report</h1><ul>"
    for msg, count in report.items():
        html += f"<li>{msg}: {count}</li>"
    html += "</ul></body></html>"
    with open(report_file, "w") as f:
        f.write(html)


def main() -> None:
    # Create dummy log file if not exists for testing
    if not os.path.exists(CONFIG["LOG_FILE"]):
        with open(CONFIG["LOG_FILE"], "w") as f:
            f.write("2023-10-01 10:00:00 INFO User 123 logged in\n")
            f.write("2023-10-01 10:05:00 ERROR Connection failed\n")
            f.write("2023-10-01 10:10:00 ERROR Connection failed\n")

    data = extract_log_entries(CONFIG["LOG_FILE"])
    report = transform_data(data)
    load_report(report, CONFIG["REPORT_FILE"])
    print("Done.")


if __name__ == "__main__":
    main()
