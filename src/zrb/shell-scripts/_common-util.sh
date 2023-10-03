set -e
# Determine OS type
OS_TYPE=$(uname)
# Function to check if a command exists
command_exists() {
    command -v "$1" &> /dev/null
}