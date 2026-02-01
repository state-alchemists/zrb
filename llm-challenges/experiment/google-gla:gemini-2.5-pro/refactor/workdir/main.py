# etl_refactored/main.py
import os

from .config import Config
from .extract import extract_logs
from .load import generate_html_report, save_report
from .transform import transform_data


def main():
    """Main function for the ETL process."""
    config = Config()

    # Simulate database connection
    print(f"Connecting to {config.DB_HOST} as {config.DB_USER}...")

    # ETL process
    logs = extract_logs(config.LOG_FILE)
    report_data = transform_data(logs)
    html_report = generate_html_report(report_data, config.REPORT_TITLE)
    save_report(html_report, config.REPORT_FILE)


if __name__ == "__main__":
    # Create a dummy log file if it doesn't exist, for testing purposes.
    # Note: In a real application, this might be handled differently.
    if not os.path.exists(Config.LOG_FILE):
        with open(Config.LOG_FILE, "w") as f:
            f.write("2023-10-01 10:00:00 INFO User 123 logged in\\n")
            f.write("2023-10-01 10:05:00 ERROR Connection failed\\n")
            f.write("2023-10-01 10:10:00 ERROR Connection failed\\n")
    main()
