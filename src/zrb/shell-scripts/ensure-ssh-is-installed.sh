set -e
if command_exists ssh
then
    log_info "SSH is already installed."
else
    log_info "Installing SSH..."
    if [ "$OS_TYPE" = "Darwin" ]
    then
        if command_exists brew
        then
            brew install openssh
        else
            log_info "Homebrew not found. Please install Homebrew and try again."
            exit 1
        fi
    elif [ "$OS_TYPE" = "Linux" ]
    then
        if command_exists pkg
        then
            try_sudo pkg update
            try_sudo pkg install -y openssh
        elif command_exists apt
        then
            try_sudo apt update
            try_sudo apt install -y openssh-client
        elif command_exists yum
        then
            try_sudo yum install -y openssh-clients
        elif command_exists dnf
        then
            try_sudo dnf install -y openssh-clients
        elif command_exists pacman
        then
            try_sudo pacman -Syu --noconfirm openssh
        else
            log_info "No known package manager found. Please install SSH manually."
            exit 1
        fi
    else
        log_info "Unsupported OS type. Please install SSH manually."
        exit 1
    fi
fi

if command_exists sshpass
then
    log_info "SSHPass is already installed."
else
    log_info "Installing SSHPass..."
    if [ "$OS_TYPE" = "Darwin" ]
    then
        if command_exists brew
        then
            brew install https://raw.githubusercontent.com/kadwanev/bigboybrew/master/Library/Formula/sshpass.rb
        else
            log_info "Homebrew not found. Please install Homebrew and try again."
            exit 1
        fi
    elif [ "$OS_TYPE" = "Linux" ]
    then
        if command_exists pkg
        then
            try_sudo pkg update
            try_sudo pkg install -y sshpass
        elif command_exists apt
        then
            try_sudo apt update
            try_sudo apt install -y sshpass
        elif command_exists yum
        then
            try_sudo yum install -y sshpass
        elif command_exists dnf
        then
            try_sudo dnf install -y sshpass
        elif command_exists pacman
        then
            try_sudo pacman -Syu --noconfirm sshpass
        else
            log_info "No known package manager found. Please install SSHPass manually."
            exit 1
        fi
    else
        log_info "Unsupported OS type. Please install SSHPass manually."
        exit 1
    fi
fi