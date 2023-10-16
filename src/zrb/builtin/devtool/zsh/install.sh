set -e

# Determine OS type
OS_TYPE=$(uname)

# Function to check if a command exists
command_exists() {
    command -v "$1" &> /dev/null
}

# Install Zsh
if command_exists zsh
then
    echo "zsh is already installed."
else
    echo "Installing zsh..."
    if [ "$OS_TYPE" = "Darwin" ]
    then
        if command_exists brew
        then
            brew install zsh
        else
            echo "Homebrew not found. Please install Homebrew and try again."
            exit 1
        fi
    elif [ "$OS_TYPE" = "Linux" ]
    then
        if command_exists apt
        then
            sudo apt update
            sudo apt install -y zsh
        elif command_exists yum
        then
            sudo yum install -y zsh
        elif command_exists dnf
        then
            sudo dnf install -y zsh
        elif command_exists pacman
        then
            sudo pacman -Syu --noconfirm zsh
        elif command_exists snap
        then
            sudo snap install zsh
        else
            echo "No known package manager found. Please install zsh manually."
            exit 1
        fi
    else
        echo "Unsupported OS type. Please install zsh manually."
        exit 1
    fi
fi

if command_exists chsh
then
    echo "Changing default shell to zsh..."
    sudo chsh -s "$(command -v zsh)"
else
    echo "chsh command not found. Please change the default shell manually."
fi

echo "Installing oh-my-zsh"
sh -c "$(curl -fsSL https://raw.github.com/ohmyzsh/ohmyzsh/master/tools/install.sh)" "" --unattended

echo "Installing zinit"
bash -c "$(curl -fsSL https://git.io/zinit-install)"