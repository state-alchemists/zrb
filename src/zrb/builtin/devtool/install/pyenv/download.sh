if [ ! -d "${HOME}/.pyenv" ]
then
    if [ "$OS_TYPE" = "Darwin" ]
    then
        if command_exists brew
        then
            brew install openssl readline sqlite3 xz zlib tcl-tk
        else
            log_info "Brew not found, continuing anyway"
        fi
    elif [ "$OS_TYPE" = "Linux" ]
    then
        if command_exists pkg
        then
            try_sudo pkg update
            try_sudo pkg install -y build-essential
        elif command_exists apt
        then
            try_sudo apt update
            try_sudo apt install -y build-essential libssl-dev zlib1g-dev \
    libbz2-dev libreadline-dev libsqlite3-dev curl \
    libncursesw5-dev xz-utils tk-dev libxml2-dev libxmlsec1-dev libffi-dev liblzma-dev
        elif command_exists yum
        then
            try_sudo yum install -y gcc make patch zlib-devel bzip2 bzip2-devel readline-devel sqlite sqlite-devel openssl-devel tk-devel libffi-devel xz-devel
        elif command_exists dnf
        then
            try_sudo dnf install -y make gcc patch zlib-devel bzip2 bzip2-devel readline-devel sqlite sqlite-devel openssl-devel tk-devel libffi-devel xz-devel libuuid-devel gdbm-libs libnsl2
        elif command_exists pacman
        then
            try_sudo pacman -Syu --noconfirm base-devel openssl zlib xz tk
        elif command_exists apk
        then
            try_sudo apk add --no-cache git bash build-base libffi-dev openssl-dev bzip2-dev zlib-dev xz-dev readline-dev sqlite-dev tk-dev
        else
            try_sudo log_info "No known package manager found, continuing anyway"
        fi
    else
        log_info "Unknown OS, cannot install pre-requisites, continuing anyway"
    fi
    log_info "Download Pyenv"
    curl https://pyenv.run | bash
else
    log_info "Pyenv already exists"
fi