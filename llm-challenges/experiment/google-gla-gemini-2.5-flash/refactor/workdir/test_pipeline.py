
import os
import unittest
import sqlite3
from pipeline_refactored import proc_data
from unittest.mock import patch, mock_open

# Mock environment variables for consistent testing
TEST_DB_PATH = "test_metrics.db"
TEST_LOG_FILE = "test_server.log"

class TestPipelineRefactored(unittest.TestCase):

    def setUp(self):
        # Ensure clean slate before each test
        if os.path.exists(TEST_DB_PATH):
            os.remove(TEST_DB_PATH)
        if os.path.exists(TEST_LOG_FILE):
            os.remove(TEST_LOG_FILE)
        if os.path.exists("report.html"):
            os.remove("report.html")

        # Create a dummy log file for testing
        with open(TEST_LOG_FILE, "w") as f:
            f.write("2024-01-01 12:00:00 INFO User 42 logged in\n")
            f.write("2024-01-01 12:05:00 ERROR Database timeout\n")
            f.write("2024-01-01 12:05:05 ERROR Database timeout\n")
            f.write("2024-01-01 12:08:00 INFO API /users/profile took 250ms\n")
            f.write("2024-01-01 12:09:00 WARN Memory usage at 87%\n")
            f.write("2024-01-01 12:10:00 INFO User 42 logged out\n")
            f.write("2024-01-01 12:15:00 INFO User 43 logged in\n")
            f.write("2024-01-01 12:20:00 INFO API /data took 100ms\n")
            f.write("2024-01-01 12:21:00 ERROR Connection reset\n")


    @patch.dict(os.environ, {
        'DB_PATH': TEST_DB_PATH,
        'LOG_FILE': TEST_LOG_FILE,
        'DB_HOST': 'localhost',
        'DB_PORT': '5432',
        'DB_USER': 'testuser',
        'DB_PASS': 'testpass'
    })
    def test_report_generation_and_db_population(self):
        proc_data() # Call the main function (formerly proc_data)

        # 1. Verify report.html content
        self.assertTrue(os.path.exists("report.html"))
        with open("report.html", "r") as f:
            content = f.read()
            self.assertIn("<h1>Error Summary</h1>", content)
            self.assertIn("<li><b>Database timeout</b>: 2 occurrences</li>", content)
            self.assertIn("<li><b>Connection reset</b>: 1 occurrences</li>", content)
            self.assertIn("<h2>API Latency</h2>", content)
            self.assertIn("<tr><td>/users/profile</td><td>250.0</td></tr>", content)
            self.assertIn("<tr><td>/data</td><td>100.0</td></tr>", content)
            self.assertIn("<h2>Active Sessions</h2>", content)
            self.assertIn("<p>1 user(s) currently active</p>", content) # User 43 logged in, 42 logged out

        # 2. Verify database content
        conn = sqlite3.connect(TEST_DB_PATH)
        c = conn.cursor()

        # Check errors table
        c.execute("SELECT message, count FROM errors ORDER BY message")
        errors = c.fetchall()
        self.assertEqual(len(errors), 2)
        self.assertEqual(errors[0], ("Connection reset", 1))
        self.assertEqual(errors[1], ("Database timeout", 2))

        # Check api_metrics table
        c.execute("SELECT endpoint, avg_ms FROM api_metrics ORDER BY endpoint")
        api_metrics = c.fetchall()
        self.assertEqual(len(api_metrics), 2)
        self.assertEqual(api_metrics[0], ("/data", 100.0))
        self.assertEqual(api_metrics[1], ("/users/profile", 250.0))

        conn.close()

    def tearDown(self):
        # Clean up created files
        if os.path.exists(TEST_DB_PATH):
            os.remove(TEST_DB_PATH)
        if os.path.exists(TEST_LOG_FILE):
            os.remove(TEST_LOG_FILE)
        if os.path.exists("report.html"):
            os.remove("report.html")

if __name__ == '__main__':
    unittest.main()
