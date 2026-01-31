import datetime
import os
import re
from typing import List, Dict, Any


class LogParser:
    def __init__(self, log_file: str):
        self.log_file = log_file

    def extract(self) -> List[Dict[str, Any]]:
        """
        Extract data from the log file.

        Returns:
            List of extracted log entries as dictionaries.
        """
        data = []
        log_pattern = re.compile(r"(?P<date>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) (?P<type>ERROR|INFO) (?P<message>.+)")
        if os.path.exists(self.log_file):
            with open(self.log_file, "r") as f:
                lines = f.readlines()
                for line in lines:
                    match = log_pattern.match(line.strip())
                    if match:
                        entry = match.groupdict()
                        if entry['type'] == 'INFO' and 'User' in entry['message']:
                            user_id = self._extract_user_id(entry['message'])
                            entry.update({'type': 'USER_ACTION', 'user': user_id})
                        data.append(entry)
        return data

    def _extract_user_id(self, message: str) -> str:
        """
        Extract user ID from message.

        Args:
            message: The log message containing the user information.

        Returns:
            Extracted user ID as a string.
        """
        user_id_match = re.search(r"User (\d+)", message)
        return user_id_match.group(1) if user_id_match else ""


class Reporter:
    def load_and_report(self, data: List[Dict[str, Any]], db_host: str, db_user: str) -> None:
        """
        Simulate loading data into a database and generating a report.

        Args:
            data: List of log entries.
            db_host: Database host.
            db_user: Database user.
        """
        print(f"Connecting to {db_host} as {db_user}...")
        report = self._transform(data)
        self._generate_html_report(report)

    def _transform(self, data: List[Dict[str, Any]]) -> Dict[str, int]:
        """
        Transform extracted data into a report format.

        Args:
            data: List of log entries.

        Returns:
            Aggregated report.
        """
        report = {}
        for item in data:
            if item["type"] == "ERROR":
                if item["message"] not in report:
                    report[item["message"]] = 0
                report[item["message"]] += 1
        return report

    def _generate_html_report(self, report: Dict[str, int]) -> None:
        """
        Generate an HTML report from the aggregated data.

        Args:
            report: Dictionary containing the aggregated report data.
        """
        html = "<html><body><h1>Report</h1><ul>"
        for k, v in report.items():
            html += f"<li>{k}: {v}</li>"
        html += "</ul></body></html>"
        with open("report.html", "w") as f:
            f.write(html)
        print("Report generated: report.html")


class ETLProcess:
    def __init__(self, config: Dict[str, str]):
        self.config = config
        self.parser = LogParser(self.config['LOG_FILE'])
        self.reporter = Reporter()

    def run(self):
        """
        Run the ETL process: Extract, Transform, and Load/Report.
        """
        data = self.parser.extract()
        self.reporter.load_and_report(data, self.config['DB_HOST'], self.config['DB_USER'])


def setup_dummy_data(log_file: str) -> None:
    """
    Create a dummy log file for testing.

    Args:
        log_file: Path to the log file.
    """
    if not os.path.exists(log_file):
        with open(log_file, "w") as f:
            f.write("2023-10-01 10:00:00 INFO User 123 logged in\n")
            f.write("2023-10-01 10:05:00 ERROR Connection failed\n")
            f.write("2023-10-01 10:10:00 ERROR Connection failed\n")


def main() -> None:
    setup_dummy_data(os.getenv('LOG_FILE', 'server.log'))
    config = {
        'DB_HOST': os.getenv('DB_HOST', 'localhost'),
        'DB_USER': os.getenv('DB_USER', 'admin'),
        'LOG_FILE': os.getenv('LOG_FILE', 'server.log'),
    }
    etl = ETLProcess(config)
    etl.run()


if __name__ == "__main__":
    main()
