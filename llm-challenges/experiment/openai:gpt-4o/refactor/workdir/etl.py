import datetime
import os
import re
from typing import List, Dict, Any

# Environment-based configuration
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_USER = os.getenv('DB_USER', 'admin')
DB_PASS = os.getenv('DB_PASS', 'password123')
LOG_FILE = os.getenv('LOG_FILE', 'server.log')


def extract_data(file_path: str) -> List[Dict[str, Any]]:
    data = []
    if os.path.exists(file_path):
        with open(file_path, 'r') as file:
            for line in file:
                # Using regex for robust parsing
                error_match = re.match(r"^(\S+ \S+) ERROR (.+)$", line)
                info_match = re.match(r"^(\S+ \S+) INFO User (\d+) .*$", line)
                if error_match:
                    data.append({"d": error_match.group(1), "t": "ERR", "m": error_match.group(2).strip()})
                elif info_match:
                    data.append({"d": info_match.group(1), "t": "USR", "u": info_match.group(2)})
    return data


def transform_data(data: List[Dict[str, Any]]) -> Dict[str, int]:
    error_summary = {}
    for entry in data:
        if entry["t"] == "ERR":
            msg = entry["m"]
            if msg not in error_summary:
                error_summary[msg] = 0
            error_summary[msg] += 1
    return error_summary


def load_data_summary(error_summary: Dict[str, int]) -> None:
    # Generate HTML report (remains unchanged)
    html_output = "<html>\n<head><title>System Report</title></head>\n<body>\n"
    html_output += "<h1>Error Summary</h1>\n<ul>\n"
    for err_msg, count in error_summary.items():
        html_output += f"<li><b>{err_msg}</b>: {count} occurrences</li>\n"
    html_output += "</ul>\n</body>\n</html>"

    with open("report.html", "w") as f:
        f.write(html_output)

    print(f"Report generated at {datetime.datetime.now()}")


def main() -> None:
    # Check LOG_FILE exists or create with dummy data (for development)
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, "w") as f:
            f.write("2024-01-01 12:00:00 INFO User 42 logged in\n")
            f.write("2024-01-01 12:05:00 ERROR Database timeout\n")
            f.write("2024-01-01 12:05:05 ERROR Database timeout\n")
            f.write("2024-01-01 12:10:00 INFO User 42 logged out\n")

    print(f"Connecting to {DB_HOST} as {DB_USER}...")
    raw_data = extract_data(LOG_FILE)
    summary = transform_data(raw_data)
    load_data_summary(summary)


if __name__ == "__main__":
    main()
