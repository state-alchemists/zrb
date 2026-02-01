import os
import re
from typing import Dict, List

# Configuration
CONFIG = {
    "LOG_FILE": "server.log",
    "DB_HOST": "localhost",
    "DB_USER": "admin",
    "REPORT_FILE": "report.html",
}

LOG_REGEX = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) (ERROR|INFO) (.*)$")


def extract_logs(log_file: str) -> List[Dict[str, str]]:
    """Extract log entries using robust regex parsing"""
    logs = []
    if not os.path.exists(log_file):
        return logs

    with open(log_file, "r") as f:
        for line in f:
            line = line.strip()
            match = LOG_REGEX.match(line)
            if not match:
                continue

            timestamp, level, message = match.groups()
            if level == "ERROR":
                logs.append(
                    {
                        "type": "ERROR",
                        "timestamp": timestamp,
                        "message": message.strip(),
                    }
                )
            elif level == "INFO" and "User" in message:
                user_match = re.search(r"User (\d+)", message)
                if user_match:
                    logs.append(
                        {
                            "type": "USER_ACTION",
                            "timestamp": timestamp,
                            "user_id": user_match.group(1),
                        }
                    )
    return logs


def transform(logs: List[Dict[str, str]]) -> Dict[str, int]:
    """Transform error logs into aggregated report data"""
    report = {}
    for log in logs:
        if log["type"] == "ERROR":
            msg = log["message"]
            report[msg] = report.get(msg, 0) + 1
    return report


def load_report(report: Dict[str, int], output_path: str):
    """Generate HTML report from transformed data"""
    html = "<html><body><h1>Report</h1><ul>"
    for message, count in report.items():
        html += f"<li>{message}: {count}</li>"
    html += "</ul></body></html>"

    with open(output_path, "w") as f:
        f.write(html)


def main():
    # Create test data if needed
    if not os.path.exists(CONFIG["LOG_FILE"]):
        with open(CONFIG["LOG_FILE"], "w") as f:
            f.write("2023-10-01 10:00:00 INFO User 123 logged in\n")
            f.write("2023-10-01 10:05:00 ERROR Connection failed\n")
            f.write("2023-10-01 10:10:00 ERROR Connection failed\n")

    # ETL execution
    logs = extract_logs(CONFIG["LOG_FILE"])
    report_data = transform(logs)
    load_report(report_data, CONFIG["REPORT_FILE"])

    # Simulated DB interaction
    print(f"Connecting to {CONFIG['DB_HOST']} as {CONFIG['DB_USER']}...")
    print("Done.")


if __name__ == "__main__":
    main()
