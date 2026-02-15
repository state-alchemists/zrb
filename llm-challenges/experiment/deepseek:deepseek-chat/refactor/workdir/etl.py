#!/usr/bin/env python3
"""
Professional ETL Pipeline for Log Processing

Refactored version with:
- Environment variable configuration (DB_HOST, DB_USER, DB_PASSWORD, LOG_FILE)
- Modular ETL architecture (Extract, Transform, Load)
- Robust parsing with regex patterns
- Type hints and proper error handling
- Preserved report.html output format
"""

import os
import re
from datetime import datetime
from typing import List, Dict, Optional
from dataclasses import dataclass
from enum import Enum
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class LogLevel(Enum):
    INFO = "INFO"
    ERROR = "ERROR"
    WARNING = "WARNING"
    DEBUG = "DEBUG"


@dataclass
class LogEntry:
    timestamp: str
    level: LogLevel
    message: str
    user_id: Optional[str] = None


class Config:
    """Configuration manager using environment variables."""
    
    @staticmethod
    def get(key: str, default: str) -> str:
        return os.getenv(key, default)
    
    @classmethod
    def database_host(cls) -> str:
        return cls.get("DB_HOST", "localhost")
    
    @classmethod
    def database_user(cls) -> str:
        return cls.get("DB_USER", "admin")
    
    @classmethod
    def database_password(cls) -> str:
        return cls.get("DB_PASSWORD", "password123")
    
    @classmethod
    def log_file(cls) -> str:
        return cls.get("LOG_FILE", "server.log")
    
    @classmethod
    def validate(cls) -> None:
        """Warn about insecure defaults."""
        if cls.database_password() == "password123":
            logger.warning("Using default database password. Set DB_PASSWORD for production.")
        if cls.database_user() == "admin":
            logger.warning("Using default database user. Set DB_USER for production.")


class LogParser:
    """Robust log parser using regex patterns."""
    
    LOG_PATTERN = re.compile(r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) (\w+) (.+)$')
    USER_PATTERN = re.compile(r'User (\d+)')
    
    @classmethod
    def parse_line(cls, line: str) -> Optional[LogEntry]:
        """Parse a single log line."""
        line = line.strip()
        if not line:
            return None
        
        match = cls.LOG_PATTERN.match(line)
        if not match:
            logger.warning(f"Failed to parse: {line[:50]}...")
            return None
        
        timestamp, level_str, message = match.groups()
        
        try:
            level = LogLevel(level_str)
        except ValueError:
            logger.warning(f"Unknown log level: {level_str}")
            return None
        
        # Extract user ID if present
        user_id = None
        if level == LogLevel.INFO:
            user_match = cls.USER_PATTERN.search(message)
            if user_match:
                user_id = user_match.group(1)
        
        return LogEntry(timestamp, level, message, user_id)
    
    @classmethod
    def parse_file(cls, filepath: str) -> List[LogEntry]:
        """Parse all lines from a log file."""
        entries = []
        
        if not os.path.exists(filepath):
            logger.error(f"Log file not found: {filepath}")
            return entries
        
        try:
            with open(filepath, 'r') as f:
                for line_num, line in enumerate(f, 1):
                    entry = cls.parse_line(line)
                    if entry:
                        entries.append(entry)
            
            logger.info(f"Parsed {len(entries)} entries from {filepath}")
            return entries
            
        except IOError as e:
            logger.error(f"Failed to read {filepath}: {e}")
            return entries


class DataProcessor:
    """Process and transform log data."""
    
    @staticmethod
    def extract_errors(entries: List[LogEntry]) -> List[Dict]:
        """Extract ERROR entries."""
        return [
            {"timestamp": e.timestamp, "message": e.message, "type": "ERR"}
            for e in entries if e.level == LogLevel.ERROR
        ]
    
    @staticmethod
    def extract_user_activities(entries: List[LogEntry]) -> List[Dict]:
        """Extract user activities from INFO entries."""
        return [
            {"timestamp": e.timestamp, "user_id": e.user_id, "message": e.message, "type": "USR"}
            for e in entries if e.level == LogLevel.INFO and e.user_id
        ]
    
    @staticmethod
    def count_errors(errors: List[Dict]) -> Dict[str, int]:
        """Count occurrences of each error message."""
        counts = {}
        for error in errors:
            msg = error["message"]
            counts[msg] = counts.get(msg, 0) + 1
        return counts


class DatabaseClient:
    """Mock database client."""
    
    def __init__(self, host: str, user: str, password: str):
        self.host = host
        self.user = user
        self.password = password
    
    def connect(self) -> bool:
        """Simulate database connection."""
        logger.info(f"Connecting to {self.host} as {self.user}...")
        return True
    
    def insert(self, data: List[Dict], table: str) -> bool:
        """Simulate data insertion."""
        logger.info(f"Inserting {len(data)} records into {table}...")
        return True


class ReportGenerator:
    """Generate HTML reports."""
    
    @staticmethod
    def generate_html(error_counts: Dict[str, int], output_path: str = "report.html") -> bool:
        """Generate HTML report with error summary."""
        try:
            html_lines = [
                "<html>",
                "<head><title>System Report</title></head>",
                "<body>",
                "<h1>Error Summary</h1>",
                "<ul>"
            ]
            
            for error_msg, count in sorted(error_counts.items()):
                html_lines.append(f'<li><b>{error_msg}</b>: {count} occurrences</li>')
            
            html_lines.extend(["</ul>", "</body>", "</html>"])
            
            with open(output_path, 'w') as f:
                f.write('\n'.join(html_lines))
            
            logger.info(f"Report saved to {output_path}")
            return True
            
        except IOError as e:
            logger.error(f"Failed to write report: {e}")
            return False


class ETLPipeline:
    """Main ETL pipeline orchestrator."""
    
    def __init__(self):
        Config.validate()
        
        self.log_file = Config.log_file()
        self.db_client = DatabaseClient(
            Config.database_host(),
            Config.database_user(),
            Config.database_password()
        )
        
        self.parser = LogParser()
        self.processor = DataProcessor()
        self.reporter = ReportGenerator()
    
    def run(self) -> bool:
        """Execute the complete ETL pipeline."""
        logger.info("Starting ETL pipeline")
        
        try:
            # Extract
            entries = self.parser.parse_file(self.log_file)
            if not entries:
                logger.warning("No entries parsed")
                return False
            
            # Transform
            errors = self.processor.extract_errors(entries)
            user_activities = self.processor.extract_user_activities(entries)
            error_counts = self.processor.count_errors(errors)
            
            logger.info(f"Processed: {len(errors)} errors, {len(user_activities)} user activities")
            
            # Load
            if not self.db_client.connect():
                return False
            
            self.db_client.insert(errors, "errors")
            self.db_client.insert(user_activities, "user_activities")
            
            # Generate report
            return self.reporter.generate_html(error_counts)
            
        except Exception as e:
            logger.error(f"Pipeline failed: {e}")
            return False


def create_sample_logs(filepath: str) -> None:
    """Create sample log file if it doesn't exist."""
    if not os.path.exists(filepath):
        logger.info(f"Creating sample log file: {filepath}")
        samples = [
            "2024-01-01 12:00:00 INFO User 42 logged in",
            "2024-01-01 12:05:00 ERROR Database timeout",
            "2024-01-01 12:05:05 ERROR Database timeout",
            "2024-01-01 12:10:00 INFO User 42 logged out",
        ]
        try:
            with open(filepath, 'w') as f:
                f.write('\n'.join(samples))
        except IOError as e:
            logger.error(f"Failed to create sample: {e}")


def main() -> None:
    """Main entry point."""
    log_file = Config.log_file()
    create_sample_logs(log_file)
    
    pipeline = ETLPipeline()
    success = pipeline.run()
    
    if success:
        print(f"Job finished at {datetime.now()}")
    else:
        print(f"Job failed at {datetime.now()}")
        exit(1)


if __name__ == "__main__":
    main()