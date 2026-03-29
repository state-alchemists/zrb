# ETL Log Processor

A robust, modular ETL (Extract, Transform, Load) pipeline for processing log files and generating HTML reports.

## Structure

```
workdir/
├── etl.py      # Main ETL pipeline orchestration
├── config.py   # Configuration management
├── parser.py   # Log parsing with regex
├── report.html # Generated HTML report
└── server.log  # Sample log file
```

## Key Improvements

### 1. Environmental Configuration
All configuration is now loaded from environment variables with sensible defaults:

| Variable | Default | Description |
|----------|---------|-------------|
| `DB_HOST` | `localhost` | Database host for connection |
| `DB_USER` | `admin` | Database username |
| `DB_PASSWORD` | `password123` | Database password |
| `LOG_FILE` | `server.log` | Input log file path |
| `REPORT_FILE` | `report.html` | Output report path |

**Example:**
```bash
DB_HOST="prod-db.example.com" DB_PASSWORD="secret123" python etl.py
```

### 2. Robust Log Parsing
- Uses regex-based parsing that handles variable whitespace
- Properly extracts timestamps, log levels, and messages
- Gracefully handles malformed lines

### 3. Modular Architecture
- **Extract**: `extract_logs()` - Reads and parses log files
- **Transform**: `transform_logs()` - Aggregates error statistics
- **Load**: `load_report()` - Generates HTML output

### 4. Type Safety
- Full type hints using Python's `typing` module
- Dataclasses for structured data (`LogEntry`)
- IDE-friendly type checking

### 5. Security
- HTML escaping for report output to prevent XSS
- Sensitive data handled via environment variables

## Usage

```bash
# Basic run (uses defaults)
python etl.py

# Custom log file
LOG_FILE="myapp.log" python etl.py

# Custom output
REPORT_FILE="output.html" python etl.py
```

## API

### `run_etl(log_path=None, output_path=None)`
Runs the complete ETL pipeline.

### `extract_logs(filepath=None)`
Extracts and parses log entries from a file.

### `transform_logs(entries)`
Transforms log entries into error summary statistics.

### `load_report(errors, output_path=None)`
Generates and saves the HTML report.
