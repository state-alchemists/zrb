`legacy_etl.py` is a mess. It's a monolithic script with hardcoded config and fragile string parsing.

Please refactor it to be more maintainable. It needs to follow the ETL pattern (Extract, Transform, Load), use regex for parsing, and separate configuration. Also, add type hints.

Ensure it still produces the same `report.html` output.