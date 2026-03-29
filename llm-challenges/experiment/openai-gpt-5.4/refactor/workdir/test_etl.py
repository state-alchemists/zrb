from collections import Counter
from pathlib import Path

from etl import (
    LogEntry,
    Settings,
    extract_records,
    parse_log_line,
    render_report,
    summarize_errors,
)


def test_parse_log_line_tolerates_extra_spaces() -> None:
    entry = parse_log_line("2024-01-01   12:05:00   ERROR   Database timeout   ")

    assert entry == LogEntry(
        timestamp="2024-01-01 12:05:00",
        level="ERROR",
        message="Database timeout",
    )


def test_extract_records_and_summarize_errors(tmp_path: Path) -> None:
    log_file = tmp_path / "server.log"
    log_file.write_text(
        "2024-01-01 12:00:00 INFO User 42 logged in\n"
        "2024-01-01 12:05:00 ERROR Database timeout\n"
        "2024-01-01 12:05:05 ERROR Database timeout\n"
        "2024-01-01 12:10:00 INFO   User   42   logged out\n",
        encoding="utf-8",
    )

    records = extract_records(log_file)
    summary = summarize_errors(records)

    assert len(records) == 4
    assert summary == Counter({"Database timeout": 2})


def test_render_report_matches_expected_structure() -> None:
    report = render_report(Counter({"Database timeout": 2}))

    assert report == (
        "<html>\n"
        "<head><title>System Report</title></head>\n"
        "<body>\n"
        "<h1>Error Summary</h1>\n"
        "<ul>\n"
        "<li><b>Database timeout</b>: 2 occurrences</li>\n"
        "</ul>\n"
        "</body>\n"
        "</html>"
    )


def test_settings_read_from_environment(monkeypatch) -> None:
    monkeypatch.setenv("ETL_DB_HOST", "db.internal")
    monkeypatch.setenv("ETL_DB_USER", "reporter")
    monkeypatch.setenv("ETL_DB_PASSWORD", "secret")
    monkeypatch.setenv("ETL_LOG_FILE", "/tmp/custom.log")
    monkeypatch.setenv("ETL_REPORT_FILE", "/tmp/custom-report.html")

    settings = Settings.from_env()

    assert settings.db_host == "db.internal"
    assert settings.db_user == "reporter"
    assert settings.db_password == "secret"
    assert str(settings.log_file) == "/tmp/custom.log"
    assert str(settings.report_file) == "/tmp/custom-report.html"
