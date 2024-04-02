if [ ! -f "./awscliv2.zip" ]
then
    log_info "Download AWS CLI"
    curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
else
    log_info "AWS CLI already downloaded"
fi

if command_exists unzip
then
    log_info "unzip is already installed."
else
    log_info "Installing unzip..."
    if [ "$OS_TYPE" = "Darwin" ]
    then
        if command_exists brew
        then
            brew install unzip
        else
            log_info "Homebrew not found. Please install Homebrew and try again."
            exit 1
        fi
    elif [ "$OS_TYPE" = "Linux" ]
    then
        if command_exists pkg
        then
            try_sudo pkg update
            try_sudo pkg install -y unzip
        elif command_exists apt
        then
            try_sudo add-apt-repository ppa:maveonair/unzip-editor -y
            try_sudo apt update
            try_sudo apt install -y unzip
        elif command_exists yum
        then
            try_sudo yum install -y unzip
        elif command_exists dnf
        then
            try_sudo dnf copr enable varlad/unzip
            try_sudo dnf install -y unzip
        elif command_exists pacman
        then
            try_sudo pacman -Syu --noconfirm unzip
        elif command_exists snap
        then
            try_sudo snap install unzip
        else
            log_info "No known package manager found. Please install unzip manually."
            exit 1
        fi
    else
        log_info "Unsupported OS type. Please install unzip manually."
        exit 1
    fi
fi

log_info "Unzip AWS CLI"
unzip awscliv2.zip
log_info "Install AWS CLI"
sudo ./aws/install --update
