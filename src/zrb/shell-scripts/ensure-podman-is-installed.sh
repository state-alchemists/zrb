set -e
if command_exists podman
then
    log_info "Podman is already installed."
else
    log_info "Installing Podman..."
    if [ "$OS_TYPE" = "Darwin" ]
    then
        if command_exists brew
        then
            brew install --cask podman
            log_info "Please start Podman before proceeding."
        else
            log_info "Homebrew not found. Please install Homebrew and try again."
            exit 1
        fi
    elif [ "$OS_TYPE" = "Linux" ]
    then
        if command_exists apt
        then
            try_sudo apt update
            try_sudo apt install -y podman
        elif command_exists yum
        then
            try_sudo yum install -y podman
        elif command_exists dnf
        then
            try_sudo dnf install -y podman
        elif command_exists pacman
        then
            try_sudo pacman -Syu --noconfirm podman
        else
            log_info "No known package manager found. Please install Podman manually."
            exit 1
        fi
    else
        log_info "Unsupported OS type. Please install Podman manually."
        exit 1
    fi
fi

if ! command_exists podman-compose
then
    log_info "Installing Podman Compose plugin..."
    pip install podman-compose
fi

# Check Podman Compose plugin installation
if command_exists podman && command_exists podman-compose
then
    log_info "Podman Compose plugin is already installed."
else
    log_info "Podman Compose plugin is not installed or podman is not running. Please check your installation."
    exit 1
fi