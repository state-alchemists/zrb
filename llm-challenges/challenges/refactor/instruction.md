Refactor the `legacy_etl.py` script. 
1. Isolate the "Extract", "Transform", and "Load/Report" phases into separate functions or classes.
2. Remove the global configuration variables and use `os.getenv` or a configuration object/dictionary.
3. Improve the log parsing logic (maybe use regex).
4. Ensure the file creation/dummy data generation is separated from the main logic (e.g., in a `setup` fixture or separate function only called if needed).
5. Add type hints and docstrings.