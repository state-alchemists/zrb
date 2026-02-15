# settings.py
import os
from dotenv import load_dotenv

# Load environment variables from a .env file if it exists
load_dotenv()

# --- Database Configuration ---
DB_HOST: str = os.getenv("DB_HOST", "localhost")
DB_USER: str = os.getenv("DB_USER", "admin")
DB_PASSWORD: str = os.getenv("DB_PASSWORD", "password123")

# --- File Paths ---
LOG_FILE_PATH: str = os.getenv("LOG_FILE_PATH", "server.log")
REPORT_FILE_PATH: str = os.getenv("REPORT_FILE_PATH", "report.html")
