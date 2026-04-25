The `pipeline.py` script processes server logs and generates a report. It works, but it's a security and maintenance nightmare:

- Credentials and paths are hardcoded
- SQL queries are built with string formatting — a textbook injection risk
- All logic is crammed into one function
- Log parsing is fragile (no regex)
- No type hints or documentation

Refactor it. Requirements:
1. Use environment variables for all config (DB path, log file path, credentials)
2. Fix the SQL injection — use parameterized queries
3. Break it into well-named functions following Extract → Transform → Load
4. Use regex for log line parsing
5. Add type hints and docstrings

The `report.html` output must still be produced with the same information (error summary, API latency table, active session count). You may rename the file to `pipeline_refactored.py` if you prefer.
