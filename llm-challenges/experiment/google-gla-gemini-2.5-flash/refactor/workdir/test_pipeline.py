
import pytest
import os
import sqlite3
import datetime
from unittest.mock import patch, MagicMock

# Assuming pipeline.py is in the same directory
import pipeline_refactored

@pytest.fixture
def setup_teardown_env():
    # Setup: Create temporary log file and database paths
    test_log_file = "test_server.log"
    test_db_path = "test_metrics.db"

    # Ensure clean state by removing any existing test files
    if os.path.exists(test_log_file):
        os.remove(test_log_file)
    if os.path.exists(test_db_path):
        os.remove(test_db_path)
    if os.path.exists("report.html"):
        os.remove("report.html")

    # Write sample log content to the temporary log file
    with open(test_log_file, "w") as f:
        f.write("2024-01-01 12:00:00 INFO User 42 logged in\n")
        f.write("2024-01-01 12:05:00 ERROR Database timeout\n")
        f.write("2024-01-01 12:05:05 ERROR Database timeout\n")
        f.write("2024-01-01 12:08:00 INFO API /users/profile took 250ms\n")
        f.write("2024-01-01 12:09:00 WARN Memory usage at 87%\n")
        f.write("2024-01-01 12:10:00 INFO User 42 logged out\n")
        f.write("2024-01-01 12:15:00 INFO User 100 logged in\n") # To test active sessions

    yield {
        "test_log_file": test_log_file,
        "test_db_path": test_db_path,
    }

    # Teardown: Remove temporary files
    if os.path.exists(test_log_file):
        os.remove(test_log_file)
    if os.path.exists(test_db_path):
        os.remove(test_db_path)
    if os.path.exists("report.html"):
        os.remove("report.html")


def test_proc_data_generates_expected_output(setup_teardown_env):
    env = setup_teardown_env
    test_db_path = env["test_db_path"]
    # test_report_file is no longer passed as part of env

    # Run the function to be tested
    os.environ['LOG_FILE'] = env["test_log_file"]
    os.environ['DB_PATH'] = env["test_db_path"]
    os.environ['DB_HOST'] = "test_host"
    os.environ['DB_PORT'] = "1234"
    os.environ['DB_USER'] = "test_user"
    os.environ['DB_PASS'] = "test_pass"

    pipeline_refactored.proc_data()

    # Clean up environment variables
    del os.environ['LOG_FILE']
    del os.environ['DB_PATH']
    del os.environ['DB_HOST']
    del os.environ['DB_PORT']
    del os.environ['DB_USER']
    del os.environ['DB_PASS']


    # Assertions for Database content
    conn = sqlite3.connect(test_db_path)
    cursor = conn.cursor()

    # Check errors table
    cursor.execute("SELECT message, count FROM errors ORDER BY message")
    errors = cursor.fetchall()
    assert len(errors) == 1
    assert errors[0][0] == "Database timeout"
    assert errors[0][1] == 2

    # Check api_metrics table
    cursor.execute("SELECT endpoint, avg_ms FROM api_metrics ORDER BY endpoint")
    api_metrics = cursor.fetchall()
    assert len(api_metrics) == 1
    assert api_metrics[0][0] == "/users/profile"
    assert api_metrics[0][1] == 250.0

    conn.close()

    # Assertions for Report content
    assert os.path.exists("report.html")
    with open("report.html", "r") as f:
        report_content = f.read()

    assert "<h1>Error Summary</h1>" in report_content
    assert "<li><b>Database timeout</b>: 2 occurrences</li>" in report_content
    assert "<h2>API Latency</h2>" in report_content
    assert "<table border='1'>" in report_content
    assert "<tr><th>Endpoint</th><th>Avg (ms)</th></tr>" in report_content
    assert "<tr><td>/users/profile</td><td>250.0</td></tr>" in report_content
    assert "<h2>Active Sessions</h2>" in report_content
    assert "<p>1 user(s) currently active</p>" in report_content # User 100 logged in, User 42 logged out

    # Ensure no specific connection details are in the output HTML for now
    assert "Connecting to localhost:5432 as admin..." not in report_content

