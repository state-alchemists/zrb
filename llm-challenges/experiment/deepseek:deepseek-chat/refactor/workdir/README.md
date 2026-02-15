# Refactored ETL Pipeline

## Overview
This is a professional refactoring of the original `etl.py` script into a maintainable, robust ETL pipeline with proper configuration management, error handling, and type hints.

## Key Improvements

### 1. **Configuration Management**
- **Environment Variables**: All configuration is now managed via environment variables
- **Defaults**: Sensible defaults provided for development
- **Security**: Warnings for insecure default credentials

```bash
# Configuration via environment variables
export DB_HOST=production-db.company.com
export DB_USER=etl_service_account
export DB_PASSWORD=super_secure_password
export LOG_FILE=/var/log/app/server.log
```

### 2. **Modular Architecture**
The monolithic function has been refactored into clean, single-responsibility classes:

- **`Config`**: Configuration management
- **`LogParser`**: Robust log parsing with regex patterns
- **`DataProcessor`**: Data transformation and aggregation
- **`DatabaseClient`**: Database operations (currently mocked)
- **`ReportGenerator`**: HTML report generation
- **`ETLPipeline`**: Main orchestrator

### 3. **Robust Error Handling**
- Graceful handling of malformed log lines
- Proper logging at different levels (INFO, WARNING, ERROR)
- Validation of configuration
- Type hints for better IDE support and maintainability

### 4. **Preserved Output**
The `report.html` output format is **exactly preserved** to maintain compatibility with existing systems.

## Usage

### Basic Usage
```bash
python etl.py
```

### With Custom Configuration
```bash
DB_HOST=prod-db DB_USER=admin DB_PASSWORD=secret LOG_FILE=app.log python etl.py
```

### In Production
```bash
# Set environment variables in your deployment
export DB_HOST=${DATABASE_HOST}
export DB_USER=${DATABASE_USER}
export DB_PASSWORD=${DATABASE_PASSWORD}
export LOG_FILE=${LOG_PATH}

# Run the pipeline
python etl.py
```

## Log Format Requirements
The parser expects logs in this format:
```
YYYY-MM-DD HH:MM:SS LEVEL Message content
```

### Supported Log Levels
- `INFO`
- `ERROR`
- `WARNING`
- `DEBUG`

### User Activity Detection
INFO messages containing "User {ID}" will be extracted as user activities:
```
2024-01-01 12:00:00 INFO User 42 logged in
```

## Error Handling
- Malformed lines are logged as warnings and skipped
- Unknown log levels are logged as warnings and skipped
- Missing log files result in error logs
- Database connection failures are properly handled

## Testing
The script includes a sample log generator for testing. If the specified log file doesn't exist, a sample file with test data is created.

## Dependencies
- Python 3.6+
- Standard library only (no external dependencies)

## Security Notes
1. **Never commit passwords** to version control
2. Use environment variables or secret managers in production
3. The script warns when using default credentials
4. Consider implementing actual database connectivity with connection pooling

## Future Enhancements
1. **Real Database Integration**: Replace mocked database client with actual DB connectors
2. **Metrics**: Add performance metrics and monitoring
3. **Scheduling**: Integrate with task schedulers (cron, Airflow, etc.)
4. **Testing**: Add unit tests for each component
5. **Configuration Files**: Support config files alongside environment variables

## Migration from Original Script
The refactored script is **fully backward compatible**:
- Same command-line interface
- Identical `report.html` output format
- All original functionality preserved
- Additional robustness and maintainability features added