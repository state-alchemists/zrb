"""Configuration module for ETL process."""

from dataclasses import dataclass


@dataclass
class DatabaseConfig:
    """Database connection configuration."""

    host: str
    user: str


@dataclass
class AppConfig:
    """Application configuration."""

    db_config: DatabaseConfig
    log_file: str
    report_file: str
