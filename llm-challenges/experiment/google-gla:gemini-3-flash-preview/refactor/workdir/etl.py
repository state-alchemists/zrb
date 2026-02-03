import os
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class Config:
    db_host: str = "localhost"
    db_user: str = "admin"
    log_file: str = "server.log"
    report_file: str = "report.html"


class LogETL:
    def __init__(self, config: Config):
        self.config = config
        self.log_pattern = re.compile(
            r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) (\w+) (.+)$"
        )
        self.user_pattern = re.compile(r"User (\w+)")

    def extract(self) -> List[str]:
        """Reads the log file and returns a list of lines."""
        if not os.path.exists(self.config.log_file):
            return []
        with open(self.config.log_file, "r") as f:
            return f.readlines()

    def transform(self, lines: List[str]) -> List[Dict[str, Any]]:
        """Parses log lines into structured data using regex."""
        extracted_data: List[Dict[str, Any]] = []
        for line in lines:
            match = self.log_pattern.match(line.strip())
            if not match:
                continue

            date_str, log_level, message = match.groups()

            if log_level == "ERROR":
                extracted_data.append(
                    {"date": date_str, "type": "ERROR", "msg": message}
                )
            elif log_level == "INFO" and "User" in message:
                user_match = self.user_pattern.search(message)
                if user_match:
                    user_id = user_match.group(1)
                    extracted_data.append(
                        {"date": date_str, "type": "USER_ACTION", "user": user_id}
                    )
        return extracted_data

    def load(self, data: List[Dict[str, Any]]) -> None:
        """Simulates DB load and generates the HTML report."""
        print(f"Connecting to {self.config.db_host} as {self.config.db_user}...")

        error_counts: Dict[str, int] = {}
        for item in data:
            if item["type"] == "ERROR":
                msg = item["msg"]
                error_counts[msg] = error_counts.get(msg, 0) + 1

        # Generate HTML report
        html_lines = ["<html><body><h1>Report</h1><ul>"]
        for msg, count in error_counts.items():
            html_lines.append(f"<li>{msg}: {count}</li>")
        html_lines.append("</ul></body></html>")

        html_content = "".join(html_lines)

        with open(self.config.report_file, "w") as f:
            f.write(html_content)

    def run(self) -> None:
        """Executes the ETL process."""
        lines = self.extract()
        data = self.transform(lines)
        self.load(data)
        print("Done.")


def main():
    config = Config()

    # Create dummy log file if not exists for testing (as per original script)
    if not os.path.exists(config.log_file):
        with open(config.log_file, "w") as f:
            f.write("2023-10-01 10:00:00 INFO User 123 logged in\n")
            f.write("2023-10-01 10:05:00 ERROR Connection failed\n")
            f.write("2023-10-01 10:10:00 ERROR Connection failed\n")

    etl = LogETL(config)
    etl.run()


if __name__ == "__main__":
    main()
