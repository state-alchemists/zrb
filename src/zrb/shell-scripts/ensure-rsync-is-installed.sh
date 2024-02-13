set -e
if command_exists rsync
then
    echo "Rsync is already installed."
else
    echo "Installing Rsync..."
    if [ "$OS_TYPE" = "Darwin" ]
    then
        if command_exists brew
        then
            brew install rsync
        else
            echo "Homebrew not found. Please install Homebrew and try again."
            exit 1
        fi
    elif [ "$OS_TYPE" = "Linux" ]
    then
        if command_exists pkg
        then
            try_sudo pkg update
            try_sudo pkg install -y rsync
        elif command_exists apt
        then
            try_sudo apt update
            try_sudo apt install -y rsync
        elif command_exists yum
        then
            try_sudo yum install -y rsync
        elif command_exists dnf
        then
            try_sudo dnf install -y rsync
        elif command_exists pacman
        then
            try_sudo pacman -Syu --noconfirm rsync
        else
            echo "No known package manager found. Please install Rsync manually."
            exit 1
        fi
    else
        echo "Unsupported OS type. Please install Rsync manually."
        exit 1
    fi
fi