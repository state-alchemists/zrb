import os
import re
from typing import List, Dict, Any
from config import Config

class ETLProcessor:
    """
    ETLProcessor handles the Extract, Transform, and Load operations for server logs.
    """
    def __init__(self, config: Config):
        self.config = config
        # Patterns for parsing log lines
        # Example line: 2023-10-01 10:00:00 INFO User 123 logged in
        self.log_pattern = re.compile(r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) (\S+) (.*)$')
        self.user_pattern = re.compile(r'User (\S+)')

    def extract(self) -> List[str]:
        """
        Extracts raw data from the log file.
        """
        if not os.path.exists(self.config.log_file):
            return []
        with open(self.config.log_file, "r") as f:
            return f.readlines()

    def transform(self, lines: List[str]) -> List[Dict[str, Any]]:
        """
        Transforms raw log lines into structured data using regex.
        """
        data: List[Dict[str, Any]] = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            match = self.log_pattern.match(line)
            if not match:
                continue
            
            timestamp, level, message = match.groups()
            
            if level == "ERROR":
                data.append({
                    "date": timestamp,
                    "type": "ERROR",
                    "msg": message
                })
            elif level == "INFO" and "User" in message:
                user_match = self.user_pattern.search(message)
                if user_match:
                    user_id = user_match.group(1)
                    data.append({
                        "date": timestamp,
                        "type": "USER_ACTION",
                        "user": user_id
                    })
        return data

    def load(self, data: List[Dict[str, Any]]) -> None:
        """
        Loads the structured data into a report file.
        """
        print(f"Connecting to {self.config.db_host} as {self.config.db_user}...")
        
        # Aggregate errors for the report
        error_counts: Dict[str, int] = {}
        for item in data:
            if item["type"] == "ERROR":
                msg = item["msg"]
                error_counts[msg] = error_counts.get(msg, 0) + 1

        # Generate HTML report
        html = "<html><body><h1>Report</h1><ul>"
        for msg, count in error_counts.items():
            html += f"<li>{msg}: {count}</li>"
        html += "</ul></body></html>"

        with open(self.config.report_file, "w") as f:
            f.write(html)
        
        print("Done.")

def run_etl():
    config = Config()
    
    # Ensure log file exists for demonstration if it doesn't already
    if not os.path.exists(config.log_file):
        with open(config.log_file, "w") as f:
            f.write("2023-10-01 10:00:00 INFO User 123 logged in\n")
            f.write("2023-10-01 10:05:00 ERROR Connection failed\n")
            f.write("2023-10-01 10:10:00 ERROR Connection failed\n")

    processor = ETLProcessor(config)
    
    # ETL Workflow
    raw_lines = processor.extract()
    transformed_data = processor.transform(raw_lines)
    processor.load(transformed_data)

if __name__ == "__main__":
    run_etl()
