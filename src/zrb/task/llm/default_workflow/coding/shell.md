# Shell Script Guidelines

## Core Principles

- **Safety First:** Always use `set -euo pipefail` at the start of scripts
- **Portability:** Prefer POSIX-compliant syntax when possible
- **Readability:** Use clear variable names and add comments for complex logic
- **Error Handling:** Always check command exit codes and handle failures gracefully

## Essential Script Structure

### Basic Template
```bash
#!/usr/bin/env bash

# Exit on error, undefined variables, and pipe failures
set -euo pipefail

# Script metadata
SCRIPT_NAME="$(basename "$0")"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Usage function
usage() {
    echo "Usage: $SCRIPT_NAME [OPTIONS]"
    echo "Description of script functionality"
    echo ""
    echo "Options:"
    echo "  -h, --help      Show this help message"
    echo "  -v, --verbose   Enable verbose output"
}

# Logging functions
log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $*"
}

error() {
    echo "[ERROR] $*" >&2
}

# Main function
main() {
    local verbose=false
    
    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                usage
                exit 0
                ;;
            -v|--verbose)
                verbose=true
                shift
                ;;
            -*)
                error "Unknown option: $1"
                usage
                exit 1
                ;;
            *)
                break
                ;;
        esac
    done
    
    # Main script logic here
    log "Starting script execution"
    
    # Example: Safe file operations
    if [[ ! -f "$1" ]]; then
        error "File not found: $1"
        exit 1
    fi
    
    log "Script completed successfully"
}

# Run main function with all arguments
main "$@"
```

## Safe Command Execution

### Error Handling
```bash
# Always check if commands succeed
if ! command -v docker >/dev/null 2>&1; then
    error "Docker is required but not installed"
    exit 1
fi

# Safe file operations
if [[ ! -d "$DIR" ]]; then
    mkdir -p "$DIR" || {
        error "Failed to create directory: $DIR"
        exit 1
    }
fi

# Capture command output safely
output=$(some_command 2>&1) || {
    error "Command failed: some_command"
    exit 1
}
```

### Temporary Files and Cleanup
```bash
# Use trap for cleanup
trap 'rm -f "$TEMP_FILE"' EXIT
TEMP_FILE=$(mktemp)

# Safe temporary directory
TEMP_DIR=$(mktemp -d)
trap 'rm -rf "$TEMP_DIR"' EXIT
```

## Common Patterns

### Configuration Loading
```bash
# Load environment from .env file
if [[ -f ".env" ]]; then
    set -a
    source .env
    set +a
fi

# Default values with overrides
: "${PORT:=8080}"
: "${HOST:=localhost}"
```

### Process Management
```bash
# Check if process is running
if pgrep -f "process_name" >/dev/null; then
    log "Process is already running"
    exit 0
fi

# Run command in background and capture PID
some_command &
PID=$!

# Wait for process with timeout
if wait "$PID"; then
    log "Command completed successfully"
else
    error "Command failed with exit code: $?"
fi
```

### File Operations
```bash
# Safe file copying
cp "source" "destination" || {
    error "Failed to copy file"
    exit 1
}

# Check file contents
if grep -q "pattern" "file.txt"; then
    log "Pattern found in file"
fi

# Process files line by line
while IFS= read -r line; do
    # Process each line
    echo "Processing: $line"
done < "input.txt"
```

## Best Practices

### Variable Safety
```bash
# Always quote variables
file="$1"
cp "$file" "destination/"

# Use arrays for multiple arguments
files=("file1.txt" "file2.txt")
cp "${files[@]}" "destination/"

# Use readonly for constants
readonly MAX_RETRIES=3
readonly CONFIG_FILE="config.json"
```

### Input Validation
```bash
# Validate numeric input
if [[ ! "$1" =~ ^[0-9]+$ ]]; then
    error "Invalid number: $1"
    exit 1
fi

# Validate file paths
if [[ "$1" != /* ]]; then
    error "Absolute path required: $1"
    exit 1
fi
```

### Performance and Resources
```bash
# Use subshell for isolated environment
(
    cd "$TEMP_DIR" || exit 1
    # Commands run in temp directory
)

# Limit resource usage
ulimit -n 1024  # Limit open files
```

## Debugging and Testing

### Debug Mode
```bash
# Enable debug mode with environment variable
if [[ "${DEBUG:-false}" == "true" ]]; then
    set -x
fi

# Verbose logging
if [[ "$verbose" == "true" ]]; then
    echo "Debug: Current directory: $(pwd)"
    echo "Debug: Arguments: $*"
fi
```

### Testing
```bash
# Use shellcheck for linting
# Install: https://github.com/koalaman/shellcheck

# Test script with different scenarios
./script.sh --help
./script.sh -v input_file.txt
./script.sh invalid_input
```