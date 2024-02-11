# Install Tmux
if command_exists tmux
then
    echo "tmux is already installed."
else
    echo "Installing tmux..."
    if [ "$OS_TYPE" = "Darwin" ]
    then
        if command_exists brew
        then
            brew install tmux
        else
            echo "Homebrew not found. Please install Homebrew and try again."
            exit 1
        fi
    elif [ "$OS_TYPE" = "Linux" ]
    then
        if command_exists pkg
        then
            try_sudo pkg update
            try_sudo pkg install -y tmux
        elif command_exists apt
        then
            try_sudo apt update
            try_sudo apt install -y tmux
        elif command_exists yum
        then
            try_sudo yum install -y tmux
        elif command_exists dnf
        then
            try_sudo dnf install -y tmux
        elif command_exists pacman
        then
            try_sudo pacman -Syu --noconfirm tmux
        elif command_exists snap
        then
            try_sudo snap install tmux
        else
            echo "No known package manager found. Please install tmux manually."
            exit 1
        fi
    else
        echo "Unsupported OS type. Please install tmux manually."
        exit 1
    fi
fi
