import datetime
import os
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

# --- Configuration ---
@dataclass
class Config:
    """Configuration for the ETL process."""
    db_host: str = os.getenv("DB_HOST", "localhost")
    db_user: str = os.getenv("DB_USER", "admin")
    db_password: str = os.getenv("DB_PASSWORD", "password123")
    log_file: str = os.getenv("LOG_FILE", "server.log")
    report_file: str = os.getenv("REPORT_FILE", "report.html")

# --- Domain Models ---
@dataclass
class LogEntry:
    """Represents a parsed log entry."""
    timestamp: str
    level: str
    message: str
    user_id: Optional[str] = None

# --- Extract ---
class LogExtractor:
    """Handles reading raw data from the log source."""
    
    def __init__(self, file_path: str):
        self.file_path = file_path

    def extract(self) -> List[str]:
        """Reads the log file and returns lines."""
        if not os.path.exists(self.file_path):
            print(f"Warning: Log file '{self.file_path}' not found.")
            return []
        
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                return f.readlines()
        except IOError as e:
            print(f"Error reading log file: {e}")
            return []

# --- Transform ---
class LogTransformer:
    """Parses raw logs and aggregates data."""

    # Regex to handle variable whitespace
    # Group 1: Date, Group 2: Time, Group 3: Level, Group 4: Message
    _LOG_PATTERN = re.compile(r"^(\S+)\s+(\S+)\s+(\S+)\s+(.*)$")

    def transform(self, raw_lines: List[str]) -> Dict[str, int]:
        """
        Parses raw lines and returns a count of error messages.
        
        Returns:
            Dict[str, int]: A dictionary mapping error messages to their frequency.
        """
        error_counts: Dict[str, int] = {}

        for line in raw_lines:
            line = line.strip()
            if not line:
                continue

            entry = self._parse_line(line)
            if not entry:
                continue

            if entry.level == "ERROR":
                if entry.message not in error_counts:
                    error_counts[entry.message] = 0
                error_counts[entry.message] += 1
            
            # Note: User extraction logic was in original but unused for report.
            # We keep parsing logic available but unused for now.

        return error_counts

    def _parse_line(self, line: str) -> Optional[LogEntry]:
        """Parses a single log line into a LogEntry object."""
        match = self._LOG_PATTERN.match(line)
        if not match:
            return None

        date_part = match.group(1)
        time_part = match.group(2)
        level = match.group(3)
        message = match.group(4)
        
        timestamp = f"{date_part} {time_part}"
        user_id = None

        if level == "INFO" and "User" in message:
            # Robust extraction of User ID
            # Original: "User 42 logged in" -> "42"
            user_match = re.search(r"User\s+(\S+)", message)
            if user_match:
                user_id = user_match.group(1)

        return LogEntry(
            timestamp=timestamp,
            level=level,
            message=message,
            user_id=user_id
        )

# --- Load ---
class ReportLoader:
    """Handles generating the output report and simulating DB upload."""

    def __init__(self, config: Config):
        self.config = config

    def load(self, error_counts: Dict[str, int]):
        """Generates the HTML report and simulates DB connection."""
        self._simulate_db_upload()
        self._generate_html_report(error_counts)
        print(f"Job finished at {datetime.datetime.now()}")

    def _simulate_db_upload(self):
        """Simulates connecting to the database using config credentials."""
        print(f"Connecting to {self.config.db_host} as {self.config.db_user}...")
        # Placeholder for actual DB logic

    def _generate_html_report(self, error_counts: Dict[str, int]):
        """Writes the error summary to an HTML file."""
        html_content = [
            "<html>",
            "<head><title>System Report</title></head>",
            "<body>",
            "<h1>Error Summary</h1>",
            "<ul>"
        ]

        # Use items() directly; dictionary order is preserved in modern Python (3.7+)
        for err_msg, count in error_counts.items():
            html_content.append(f"<li><b>{err_msg}</b>: {count} occurrences</li>")

        html_content.append("</ul>")
        html_content.append("</body>")
        html_content.append("</html>")

        try:
            with open(self.config.report_file, "w", encoding="utf-8") as f:
                f.write("\n".join(html_content))
        except IOError as e:
            print(f"Error writing report file: {e}")

# --- Main Execution ---
def setup_dummy_data(log_file: str):
    """Creates dummy log data for testing purposes."""
    if not os.path.exists(log_file):
        # Using print to match original script's lack of logging library
        with open(log_file, "w", encoding="utf-8") as f:
            f.write("2024-01-01 12:00:00 INFO User 42 logged in\n")
            f.write("2024-01-01 12:05:00 ERROR Database timeout\n")
            f.write("2024-01-01 12:05:05 ERROR Database timeout\n")
            f.write("2024-01-01 12:10:00 INFO User 42 logged out\n")

def main():
    # Initialize Configuration
    config = Config()

    # Ensure source data exists (Legacy behavior)
    setup_dummy_data(config.log_file)

    # ETL Process
    extractor = LogExtractor(config.log_file)
    transformer = LogTransformer()
    loader = ReportLoader(config)

    # 1. Extract
    raw_data = extractor.extract()

    # 2. Transform
    error_summary = transformer.transform(raw_data)

    # 3. Load
    loader.load(error_summary)

if __name__ == "__main__":
    main()
