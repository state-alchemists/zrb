import os
import re
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List, Optional


# --- Configuration ---
@dataclass
class Config:
    db_host: str = "localhost"
    db_user: str = "admin"
    log_file: str = "server.log"
    report_file: str = "report.html"


# --- Models ---
@dataclass
class LogEntry:
    timestamp: str
    level: str
    message: str
    user_id: Optional[str] = None


# --- ETL Components ---


class Extractor:
    def __init__(self, file_path: str):
        self.file_path = file_path

    def extract(self) -> List[str]:
        if not os.path.exists(self.file_path):
            return []
        with open(self.file_path, "r") as f:
            return f.readlines()


class Transformer:
    # Regex to capture Timestamp, Level, and Message
    # Example: 2023-10-01 10:00:00 INFO User 123 logged in
    # Group 1: Timestamp
    # Group 2: Level
    # Group 3: Message
    LOG_PATTERN = re.compile(r"^(\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2})\s+(\w+)\s+(.*)$")

    # Regex for User ID extraction
    USER_PATTERN = re.compile(r"User\s+(\d+)")

    def transform(self, raw_lines: List[str]) -> List[LogEntry]:
        entries: List[LogEntry] = []
        for line in raw_lines:
            match = self.LOG_PATTERN.match(line.strip())
            if match:
                timestamp, level, message = match.groups()
                user_id = None

                if level == "INFO":
                    user_match = self.USER_PATTERN.search(message)
                    if user_match:
                        user_id = user_match.group(1)

                # Filter logic based on original script:
                # - Keeps ERRORs
                # - Keeps INFOs if they have "User" (implied by extraction logic in original,
                #   though original script only appended to 'data' if 'User' was in msg for INFO,
                #   or if it was ERROR. Other lines were ignored.)

                if level == "ERROR":
                    entries.append(LogEntry(timestamp, level, message, None))
                elif level == "INFO" and "User" in message:
                    # Original logic:
                    # if "User" in msg: ... data.append({"date": d, "type": "USER_ACTION", "user": user_id})
                    # Note: Original script changed "type" to "USER_ACTION" for user logs.
                    # But strictly, the ETL pattern usually preserves data then aggregates.
                    # However, to produce the exact same report, we need to mimic the data selection logic.
                    entries.append(LogEntry(timestamp, "USER_ACTION", message, user_id))

        return entries

    def aggregate_errors(self, entries: List[LogEntry]) -> Dict[str, int]:
        report = defaultdict(int)
        for entry in entries:
            # Original logic: only counted items where type == "ERROR" (which meant original level was ERROR)
            # And keys were the messages.
            if entry.level == "ERROR":
                report[entry.message] += 1
        return dict(report)


class Loader:
    def __init__(self, output_file: str):
        self.output_file = output_file

    def load(self, report_data: Dict[str, int]) -> None:
        html = "<html><body><h1>Report</h1><ul>"
        for k, v in report_data.items():
            html += f"<li>{k}: {v}</li>"
        html += "</ul></body></html>"

        with open(self.output_file, "w") as f:
            f.write(html)


# --- Orchestration ---


def main():
    config = Config()

    # Create dummy log file if not exists (Preserving original behavior for testing)
    if not os.path.exists(config.log_file):
        with open(config.log_file, "w") as f:
            f.write("2023-10-01 10:00:00 INFO User 123 logged in\n")
            f.write("2023-10-01 10:05:00 ERROR Connection failed\n")
            f.write("2023-10-01 10:10:00 ERROR Connection failed\n")

    print(f"Connecting to {config.db_host} as {config.db_user}...")

    # Extract
    extractor = Extractor(config.log_file)
    raw_data = extractor.extract()

    # Transform
    transformer = Transformer()
    entries = transformer.transform(raw_data)
    report_stats = transformer.aggregate_errors(entries)

    # Load
    loader = Loader(config.report_file)
    loader.load(report_stats)

    print("Done.")


if __name__ == "__main__":
    main()
