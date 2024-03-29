# Install Docker
if command_exists docker
then
    log_info "Docker is already installed."
else
    log_info "Installing Docker..."
    if [ "$OS_TYPE" = "Darwin" ]
    then
        if command_exists brew
        then
            brew install --cask docker
            log_info "Please start Docker Desktop before proceeding."
        else
            log_info "Homebrew not found. Please install Homebrew and try again."
            exit 1
        fi
    elif [ "$OS_TYPE" = "Linux" ]
    then
        if command_exists apt
        then
            try_sudo apt update
            try_sudo apt-get remove docker docker-engine docker.io containerd runc || true
            try_sudo apt install -y apt-transport-https ca-certificates curl software-properties-common
            curl -fsSL https://download.docker.com/linux/ubuntu/gpg |try_sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
            try_sudo add-apt-repository "deb [arch=amd64] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable"
            log_info "deb [arch=amd64 signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" |try_sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
            try_sudo apt update
            try_sudo apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
        elif command_exists yum
        then
            try_sudo yum install -y docker
            try_sudo systemctl start docker
            try_sudo systemctl enable docker
        elif command_exists dnf
        then
            try_sudo dnf install -y docker
            try_sudo systemctl start docker
            try_sudo systemctl enable docker
        elif command_exists pacman
        then
            try_sudo pacman -Syu --noconfirm docker
            try_sudo systemctl start docker
            try_sudo systemctl enable docker
        else
            log_info "No known package manager found. Please install Docker manually."
            exit 1
        fi
    else
        log_info "Unsupported OS type. Please install Docker manually."
        exit 1
    fi
fi

# Install Docker Compose plugin for yum, dnf, and pacman
if command_exists docker && ! docker compose version &> /dev/null
then
    log_info "Installing Docker Compose plugin..."
    DOCKER_COMPOSE_VERSION=$(curl -s https://api.github.com/repos/docker/compose/releases/latest | grep '"tag_name":' | sed -E 's/.*"([^"]+)".*/\1/')
    curl -L "https://github.com/docker/compose/releases/download/${DOCKER_COMPOSE_VERSION}/docker-compose-linux-$(uname -m)" -o docker-compose
    chmod +x docker-compose
    mkdir -p ~/.docker/cli-plugins
    mv docker-compose ~/.docker/cli-plugins/docker-compose
fi

# Check Docker Compose plugin installation
if command_exists docker && docker compose version &> /dev/null
then
    log_info "Docker Compose plugin is already installed."
else
    log_info "Docker Compose plugin is not installed or Docker is not running. Please check your installation."
    exit 1
fi
