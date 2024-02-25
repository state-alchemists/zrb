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
        if command_exists pkg
        then
            try_sudo pkg update
            try_sudo pkg install -y zsh
        elif command_exists apt
        then
            try_sudo apt update
            try_sudo apt install -y zsh
        elif command_exists yum
        then
            try_sudo yum install -y zsh
        elif command_exists dnf
        then
            try_sudo dnf install -y zsh
        elif command_exists pacman
        then
            try_sudo pacman -Syu --noconfirm zsh
        elif command_exists snap
        then
            try_sudo snap install zsh
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
     try_sudo chsh -s zsh
else
    echo "chsh command not found. Please change the default shell manually."
fi

if [ -d "$HOME/.oh-my-zsh" ]
then
    echo "oh-my-zsh is already installed"
else
    echo "Installing oh-my-zsh"
    sh -c "$(curl -fsSL https://raw.github.com/ohmyzsh/ohmyzsh/master/tools/install.sh)" "" --unattended
fi

echo "Installing zinit"
bash -c "$(curl -fsSL https://git.io/zinit-install)"
