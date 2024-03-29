# Install Zsh
if command_exists zsh
then
    log_info "zsh is already installed."
else
    log_info "Installing zsh..."
    if [ "$OS_TYPE" = "Darwin" ]
    then
        if command_exists brew
        then
            brew install zsh
        else
            log_info "Homebrew not found. Please install Homebrew and try again."
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
            log_info "No known package manager found. Please install zsh manually."
            exit 1
        fi
    else
        log_info "Unsupported OS type. Please install zsh manually."
        exit 1
    fi
fi

if command_exists chsh
then
    log_info "Changing default shell to zsh..."
     try_sudo chsh -s zsh
else
    log_info "chsh command not found. Please change the default shell manually."
fi

if [ -d "$HOME/.oh-my-zsh" ]
then
    log_info "oh-my-zsh is already installed"
else
    log_info "Installing oh-my-zsh"
    sh -c "$(curl -fsSL https://raw.github.com/ohmyzsh/ohmyzsh/master/tools/install.sh)" "" --unattended
fi

log_info "Installing zinit"
bash -c "$(curl -fsSL https://git.io/zinit-install)"
