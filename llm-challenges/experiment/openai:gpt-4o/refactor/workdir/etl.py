import re
from typing import List, Dict
import config
import os


def extract_data(file_path: str) -> List[Dict]:
    data = []
    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            lines = f.readlines()
            for line in lines:
                match = re.match(r"^(\d+-\d+-\d+ \d+:\d+:\d+) (ERROR|INFO) (.+)", line)
                if match:
                    date, log_type, msg = match.groups()
                    if log_type == "ERROR":
                        data.append({"date": date, "type": log_type, "msg": msg.strip()})
                    elif log_type == "INFO" and "User" in msg:
                        user_search = re.search(r"User (\d+)", msg)
                        if user_search:
                            user_id = user_search.group(1)
                            data.append({"date": date, "type": "USER_ACTION", "user": user_id})
    return data


def transform_data(data: List[Dict]) -> Dict:
    report = {}
    for item in data:
        if item["type"] == "ERROR":
            if item["msg"] not in report:
                report[item["msg"]] = 0
            report[item["msg"]] += 1
    return report


def load_data(report: Dict) -> None:
    html = "<html><body><h1>Report</h1><ul>"
    for k, v in report.items():
        html += f"<li>{k}: {v}</li>"
    html += "</ul></body></html>"

    with open("report.html", "w") as f:
        f.write(html)


def main():
    data = extract_data(config.LOG_FILE)
    report = transform_data(data)
    load_data(report)
    print("Done.")


if __name__ == "__main__":
    if not os.path.exists(config.LOG_FILE):
        with open(config.LOG_FILE, "w") as f:
            f.write("2023-10-01 10:00:00 INFO User 123 logged in\n")
            f.write("2023-10-01 10:05:00 ERROR Connection failed\n")
            f.write("2023-10-01 10:10:00 ERROR Connection failed\n")
    main()