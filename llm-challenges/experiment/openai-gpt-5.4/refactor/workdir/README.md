# ETL Log Report

This project reads an application log, extracts structured events, simulates loading them to a database, and writes `report.html` with the same report format used before.

## Configuration

The script now reads configuration from environment variables instead of hardcoded values:

- `ETL_DB_HOST` (default: `localhost`)
- `ETL_DB_USER` (default: `admin`)
- `ETL_DB_PASSWORD` (default: `password123`)
- `ETL_LOG_FILE` (default: `server.log`)
- `ETL_REPORT_FILE` (default: `report.html`)

## Usage

```bash
python3 etl.py
```

Example with custom configuration:

```bash
ETL_DB_HOST=db.internal \
ETL_DB_USER=reporter \
ETL_DB_PASSWORD=secret \
python3 etl.py
```

## Notes

- Parsing is whitespace-tolerant for supported log lines.
- The generated `report.html` structure is preserved.
- A sample log file is created automatically if the configured log file does not exist.

## Tests

```bash
pytest -q
```
