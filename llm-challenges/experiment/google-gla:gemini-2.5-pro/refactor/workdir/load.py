# etl_refactored/load.py
from .models import ReportData


def generate_html_report(report_data: ReportData, title: str) -> str:
    """
    Generates an HTML report from report data.

    Args:
        report_data: The data to include in the report.
        title: The title of the report.

    Returns:
        The HTML report as a string.
    """

    html = f"<html><body><h1>{title}</h1><ul>"
    for key, value in report_data.items():
        html += f"<li>{key}: {value}</li>"
    html += "</ul></body></html>"
    return html


def save_report(html_content: str, output_file: str) -> None:
    """
    Saves the HTML report to a file.

    Args:
        html_content: The HTML content to save.
        output_file: The path to the output file.
    """
    with open(output_file, "w") as f:
        f.write(html_content)
    print("Done.")
