set -e
if command_exists docker
then
    echo "Docker is already installed."
else
    echo "Installing Docker..."
    if [ "$OS_TYPE" = "Darwin" ]
    then
        if command_exists brew
        then
            brew install --cask docker
            echo "Please start Docker Desktop before proceeding."
        else
            echo "Homebrew not found. Please install Homebrew and try again."
            exit 1
        fi
    elif [ "$OS_TYPE" = "Linux" ]
    then
        if command_exists apt
        then
            sudo apt update
            sudo apt-get remove docker docker-engine docker.io containerd runc || true
            sudo apt install -y apt-transport-https ca-certificates curl software-properties-common
            curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
            sudo add-apt-repository "deb [arch=amd64] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable"
            echo "deb [arch=amd64 signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
            sudo apt update
            sudo apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
        elif command_exists yum
        then
            sudo yum install -y docker
            sudo systemctl start docker
            sudo systemctl enable docker
        elif command_exists dnf
        then
            sudo dnf install -y docker
            sudo systemctl start docker
            sudo systemctl enable docker
        elif command_exists pacman
        then
            sudo pacman -Syu --noconfirm docker
            sudo systemctl start docker
            sudo systemctl enable docker
        else
            echo "No known package manager found. Please install Docker manually."
            exit 1
        fi
    else
        echo "Unsupported OS type. Please install Docker manually."
        exit 1
    fi
fi

if command_exists docker && ! docker compose version &> /dev/null
then
    echo "Installing Docker Compose plugin..."
    DOCKER_COMPOSE_VERSION=$(curl -s https://api.github.com/repos/docker/compose/releases/latest | grep '"tag_name":' | sed -E 's/.*"([^"]+)".*/\1/')
    curl -L "https://github.com/docker/compose/releases/download/${DOCKER_COMPOSE_VERSION}/docker-compose-linux-$(uname -m)" -o docker-compose
    chmod +x docker-compose
    mkdir -p ~/.docker/cli-plugins
    mv docker-compose ~/.docker/cli-plugins/docker-compose
fi

# Check Docker Compose plugin installation
if command_exists docker && docker compose version &> /dev/null
then
    echo "Docker Compose plugin is already installed."
else
    echo "Docker Compose plugin is not installed or Docker is not running. Please check your installation."
    exit 1
fi