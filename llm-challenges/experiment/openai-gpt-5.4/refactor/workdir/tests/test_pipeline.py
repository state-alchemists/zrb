import sqlite3
import subprocess
import sys
from pathlib import Path


def test_should_generate_report_and_store_aggregates_when_processing_log(tmp_path: Path) -> None:
    log_path = tmp_path / "server.log"
    db_path = tmp_path / "metrics.db"
    report_path = tmp_path / "report.html"

    log_path.write_text(
        "2024-01-01 12:00:00 INFO User 42 logged in\n"
        "2024-01-01 12:05:00 ERROR Database timeout\n"
        "2024-01-01 12:05:05 ERROR Database timeout\n"
        "2024-01-01 12:08:00 INFO API /users/profile took 250ms\n"
        "2024-01-01 12:09:00 WARN Memory usage at 87%\n"
        "2024-01-01 12:10:00 INFO User 42 logged out\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, "pipeline.py"],
        cwd=Path(__file__).resolve().parents[1],
        check=False,
        capture_output=True,
        text=True,
        env={
            "DB_PATH": str(db_path),
            "LOG_FILE": str(log_path),
            "REPORT_FILE": str(report_path),
            "DB_HOST": "localhost",
            "DB_PORT": "5432",
            "DB_USER": "admin",
            "DB_PASS": "password123",
        },
    )

    assert result.returncode == 0, result.stderr
    report = report_path.read_text(encoding="utf-8")
    assert "<h1>Error Summary</h1>" in report
    assert "<li><b>Database timeout</b>: 2 occurrences</li>" in report
    assert "<h2>API Latency</h2>" in report
    assert "<tr><td>/users/profile</td><td>250.0</td></tr>" in report
    assert "<h2>Active Sessions</h2>" in report
    assert "<p>0 user(s) currently active</p>" in report

    connection = sqlite3.connect(db_path)
    errors = connection.execute(
        "SELECT message, count FROM errors ORDER BY message"
    ).fetchall()
    api_metrics = connection.execute(
        "SELECT endpoint, avg_ms FROM api_metrics ORDER BY endpoint"
    ).fetchall()
    connection.close()

    assert errors == [("Database timeout", 2)]
    assert api_metrics == [('/users/profile', 250.0)]
