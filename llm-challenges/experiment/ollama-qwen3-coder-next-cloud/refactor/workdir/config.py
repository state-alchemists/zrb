"""Configuration module for ETL process.

Uses environment variables for configuration with sensible defaults.
"""

import os
from pathlib import Path


class Config:
    """ETL configuration loaded from environment variables."""

    # Database configuration
    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_USER: str = os.getenv("DB_USER", "admin")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "password123")

    # Log file configuration
    LOG_FILE: str = os.getenv("LOG_FILE", "server.log")
    REPORT_FILE: str = os.getenv("REPORT_FILE", "report.html")


# Singleton instance for easy access
config = Config()
