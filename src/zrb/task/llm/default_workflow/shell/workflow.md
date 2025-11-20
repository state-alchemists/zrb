---
description: "A workflow for writing robust, safe, and maintainable shell scripts."
---
Follow this workflow to create reliable, secure, and well-structured shell scripts.

# Core Mandates

- **Safety First:** Prevent common shell scripting pitfalls and security issues
- **Robustness:** Handle errors gracefully and predictably
- **Portability:** Write scripts that work across different environments
- **Maintainability:** Create readable, well-documented scripts

# Tool Usage Guideline
- Use `read_from_file` to analyze existing shell scripts and configurations
- Use `run_shell_command` to test shell scripts and commands
- Use `write_to_file` to create new shell scripts
- Use `search_files` to find shell patterns and conventions

# Step 1: Script Foundation

## Non-Negotiable Boilerplate
Every script MUST start with this header. No exceptions.

```bash
#!/usr/bin/env bash

# Exit on error, exit on unset variables, and exit on pipe fails.
set -euo pipefail

# Set IFS to default and save for restoration
OLD_IFS="$IFS"
IFS=$'\n\t'

# Ensure proper cleanup on exit
trap 'IFS="$OLD_IFS"' EXIT
```

## Additional Safety Options
```bash
# Treat unset variables as errors
set -u

# Exit on any error
set -e

# Exit on pipe failure
set -o pipefail

# Make sure to fail on command substitution
shopt -s inherit_errexit
```

# Step 2: Script Structure Planning

1. **Define Purpose:** Clearly understand what the script should accomplish
2. **Identify Dependencies:** Determine required commands and tools
3. **Plan Error Handling:** Design comprehensive error handling strategy
4. **Structure Functions:** Plan modular function organization
5. **Consider Portability:** Ensure compatibility with target environments

# Step 3: Implementation Standards

## Variable Safety
- **Quote Everything:** Always use `"$variable"` instead of `$variable`
- **Local Variables:** Use `local` in functions to avoid global scope pollution
- **Constants:** Use `readonly` for values that shouldn't change
- **Arrays:** Use arrays for lists instead of strings with spaces

## Function Definitions
```bash
# Standard function template
function my_function() {
    local arg1="$1"
    local arg2="$2"
    
    # Function logic here
    echo "Processing: $arg1, $arg2"
}
```

## Error Handling Patterns
```bash
# Check command existence
if ! command -v required_command &> /dev/null; then
    echo "Error: required_command not found" >&2
    exit 1
fi

# Handle command failures
important_command || {
    echo "Error: important_command failed" >&2
    exit 1
}

# Temporary file handling
tmp_file=$(mktemp)
trap 'rm -f "$tmp_file"' EXIT
```

# Step 4: Write Script Components

## Standard Script Structure
```bash
#!/usr/bin/env bash
set -euo pipefail

# Configuration section
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly SCRIPT_NAME="$(basename "$0")"

# Function definitions
function usage() {
    cat << EOF
Usage: $SCRIPT_NAME [OPTIONS]

Description of what the script does.

OPTIONS:
    -h, --help      Show this help message
    -v, --verbose   Enable verbose output
    -f, --file FILE Specify input file

EXAMPLES:
    $SCRIPT_NAME -f input.txt
    $SCRIPT_NAME --verbose

EOF
}

function log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >&2
}

function error() {
    echo "[ERROR] $*" >&2
    exit 1
}

function main() {
    local verbose=false
    local input_file=""
    
    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                usage
                exit 0
                ;;
            -v|--verbose)
                verbose=true
                ;;
            -f|--file)
                input_file="$2"
                shift
                ;;
            *)
                error "Unknown option: $1"
                ;;
        esac
        shift
    done
    
    # Main script logic
    if [[ -z "$input_file" ]]; then
        error "Input file is required"
    fi
    
    if [[ ! -f "$input_file" ]]; then
        error "File not found: $input_file"
    fi
    
    "$verbose" && log "Processing file: $input_file"
    
    # Actual work here
    process_file "$input_file"
}

# Helper functions
function process_file() {
    local file="$1"
    # File processing logic
}

# Main execution
main "$@"
```

# Step 5: Testing and Verification

1. **ShellCheck Validation:** Run `shellcheck script.sh` and fix all warnings
2. **Syntax Checking:** Run `bash -n script.sh` to check syntax
3. **Dry Run Testing:** Test with sample data and edge cases
4. **Error Scenario Testing:** Verify error handling works correctly
5. **Portability Testing:** Test on different shell versions if needed

# Step 6: Quality Assurance

## ShellCheck Compliance
- **No Warnings:** Address all ShellCheck warnings
- **Best Practices:** Follow ShellCheck recommendations
- **Security:** Eliminate potential security issues

## Code Review Checklist
- [ ] Script starts with proper shebang and safety options
- [ ] All variables are properly quoted
- [ ] Error handling is comprehensive
- [ ] Functions use `local` variables
- [ ] Temporary files are cleaned up properly
- [ ] Command existence is verified
- [ ] Exit codes are used appropriately
- [ ] Documentation is complete

# Step 7: Advanced Patterns

## Signal Handling
```bash
# Handle interrupts gracefully
function cleanup() {
    echo "Cleaning up..."
    # Cleanup logic
}

trap cleanup EXIT INT TERM
```

## Parallel Execution
```bash
# Run commands in parallel with proper error handling
function run_parallel() {
    local pids=()
    
    for item in "${items[@]}"; do
        process_item "$item" &
        pids+=($!)
    done
    
    # Wait for all processes
    for pid in "${pids[@]}"; do
        wait "$pid"
    done
}
```

## Configuration Management
```bash
# Load configuration from file
function load_config() {
    local config_file="${1:-config.sh}"
    
    if [[ -f "$config_file" ]]; then
        # shellcheck source=/dev/null
        source "$config_file"
    else
        error "Configuration file not found: $config_file"
    fi
}
```

# Step 8: Finalize and Deliver

1. **Final Testing:** Run comprehensive test scenarios
2. **Documentation:** Ensure usage instructions are clear
3. **Security Review:** Verify no security vulnerabilities
4. **Performance Check:** Ensure script runs efficiently
5. **Deployment Ready:** Confirm script is ready for production use

# Common Commands Reference

## Development
- `shellcheck script.sh`: Lint shell script
- `bash -n script.sh`: Check syntax without executing
- `bash -x script.sh`: Debug with execution tracing
- `time bash script.sh`: Measure execution time

## Testing
- Create test cases with known inputs and expected outputs
- Test edge cases and error conditions
- Verify portability across different environments
- Test with different shell versions if required

# Risk Assessment Guidelines

## Low Risk (Proceed Directly)
- Creating new utility scripts with proper safety measures
- Adding functions to existing well-structured scripts
- Running linters and syntax checkers

## Moderate Risk (Explain and Confirm)
- Modifying existing production scripts
- Scripts that modify system files
- Operations requiring elevated privileges
- Changes to critical system automation

## High Risk (Refuse and Explain)
- Scripts that could cause data loss
- Operations on system-critical paths
- Changes to security-sensitive scripts
- Scripts with potential for infinite loops or resource exhaustion