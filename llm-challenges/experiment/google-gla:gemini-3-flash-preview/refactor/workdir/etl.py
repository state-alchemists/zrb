import datetime
import os
import re
from dataclasses import dataclass
from typing import List, Dict, Optional


@dataclass
class LogEntry:
    timestamp: str
    level: str
    message: str


class Config:
    def __init__(self):
        self.db_host = os.getenv("DB_HOST", "localhost")
        self.db_user = os.getenv("DB_USER", "admin")
        self.db_pass = os.getenv("DB_PASS", "password123")
        self.log_file = os.getenv("LOG_FILE", "server.log")
        self.report_file = os.getenv("REPORT_FILE", "report.html")


class LogExtractor:
    def __init__(self, log_file: str):
        self.log_file = log_file
        # Pattern matches: YYYY-MM-DD HH:MM:SS LEVEL MESSAGE
        self.pattern = re.compile(r"^(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2}:\d{2})\s+(\w+)\s+(.*)$")

    def extract(self) -> List[LogEntry]:
        entries = []
        if not os.path.exists(self.log_file):
            return entries
        
        with open(self.log_file, "r") as f:
            for line in f:
                match = self.pattern.match(line.strip())
                if match:
                    date, time, level, message = match.groups()
                    entries.append(LogEntry(
                        timestamp=f"{date} {time}",
                        level=level,
                        message=message
                    ))
        return entries


class ReportTransformer:
    def transform_errors(self, entries: List[LogEntry]) -> Dict[str, int]:
        error_counts = {}
        for entry in entries:
            if entry.level == "ERROR":
                msg = entry.message.strip()
                error_counts[msg] = error_counts.get(msg, 0) + 1
        return error_counts


class ReportLoader:
    def __init__(self, config: Config):
        self.config = config

    def load_to_db(self):
        # Simulate DB upload as per original script
        print(f"Connecting to {self.config.db_host} as {self.config.db_user}...")
        # Insertion logic omitted as per original script

    def save_html_report(self, error_counts: Dict[str, int]):
        # Maintain exact HTML structure from original script
        out = "<html>\n<head><title>System Report</title></head>\n<body>\n"
        out += "<h1>Error Summary</h1>\n<ul>\n"
        for err_msg, count in error_counts.items():
            out += f"<li><b>{err_msg}</b>: {count} occurrences</li>\n"
        out += "</ul>\n</body>\n</html>"

        with open(self.config.report_file, "w") as f:
            f.write(out)


def run_etl():
    config = Config()
    
    # Extract
    extractor = LogExtractor(config.log_file)
    entries = extractor.extract()
    
    # Transform
    transformer = ReportTransformer()
    error_summary = transformer.transform_errors(entries)
    
    # Load
    loader = ReportLoader(config)
    loader.load_to_db()
    loader.save_html_report(error_summary)
    
    print(f"Job finished at {datetime.datetime.now()}")


if __name__ == "__main__":
    # Setup dummy data if needed (preserving original behavior)
    log_file = os.getenv("LOG_FILE", "server.log")
    if not os.path.exists(log_file):
        with open(log_file, "w") as f:
            f.write("2024-01-01 12:00:00 INFO User 42 logged in\n")
            f.write("2024-01-01 12:05:00 ERROR Database timeout\n")
            f.write("2024-01-01 12:05:05 ERROR Database timeout\n")
            f.write("2024-01-01 12:10:00 INFO User 42 logged out\n")
    
    run_etl()
