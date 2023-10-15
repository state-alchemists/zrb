set -e

# Determine OS type
OS_TYPE=$(uname)

# Function to check if a command exists
command_exists() {
    command -v "$1" &> /dev/null
}

# Install helix
if command_exists hx
then
    echo "helix is already installed."
else
    echo "Installing helix..."
    if [ "$OS_TYPE" = "Darwin" ]
    then
        if command_exists brew
        then
            brew install helix
        else
            echo "Homebrew not found. Please install Homebrew and try again."
            exit 1
        fi
    elif [ "$OS_TYPE" = "Linux" ]
    then
        if command_exists apt
        then
            sudo apt install xclip
            sudo add-apt-repository ppa:maveonair/helix-editor -y
            sudo apt update
            sudo apt install -y helix
        elif command_exists yum
        then
            sudo yum install -y helix
        elif command_exists dnf
        then
            sudo dnf copr enable varlad/helix
            sudo dnf install -y helix
        elif command_exists pacman
        then
            sudo pacman -Syu --noconfirm helix
        elif command_exists snap
        then
            sudo snap install helix
        else
            echo "No known package manager found. Please install helix manually."
            exit 1
        fi
    else
        echo "Unsupported OS type. Please install helix manually."
        exit 1
    fi
fi