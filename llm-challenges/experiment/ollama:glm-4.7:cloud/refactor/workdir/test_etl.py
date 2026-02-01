#!/usr/bin/env python3
"""Verification script to test the refactored ETL produces the same output."""
import os
import re

from etl import create_dummy_log_file, get_default_config, run_etl_pipeline


def test_output():
    """Test that refactored code produces expected output."""
    config = get_default_config()

    # Clean up previous outputs
    for f in [config.log_file, config.report_file]:
        if os.path.exists(f):
            os.remove(f)

    # Create dummy log and run ETL
    create_dummy_log_file(config.log_file)
    run_etl_pipeline(config)

    # Verify report.html exists and has correct content
    assert os.path.exists(config.report_file), "report.html was not created"

    with open(config.report_file, "r") as f:
        report_content = f.read()

    # Check essential HTML elements
    assert "<html>" in report_content, "Missing <html> tag"
    assert "<body>" in report_content, "Missing <body> tag"
    assert "<h1>Report</h1>" in report_content, "Missing report title"
    assert "<ul>" in report_content, "Missing <ul> tag"
    assert "</ul>" in report_content, "Missing </ul> tag"
    assert "</body>" in report_content, "Missing </body> tag"
    assert "</html>" in report_content, "Missing </html> tag"

    # Check error count
    assert "Connection failed: 2" in report_content, "Incorrect error count"

    print("✓ All tests passed!")
    print(f"\nGenerated report.html content:\n{report_content}")


if __name__ == "__main__":
    test_output()
