set -e
OS_TYPE=$(uname)

if [ -n "$PREFIX" ] && [ "$PREFIX" = "/data/data/com.termux/files/usr" ]
then
    IS_TERMUX=1
else
    IS_TERMUX=0
fi

log_progress() {
    echo -e "🤖 \e[0;33m${1}\e[0;0m"
}

command_exists() {
    command -v "$1" &> /dev/null
}

try_sudo() {
    if command_exists sudo
    then
        sudo $@
    else
        $@
    fi
}

register_pyenv() {
    log_progress "Registering Pyenv to $1"
    echo 'if [ -d "${HOME}/.pyenv" ]' >> $1
    echo 'then' >> $1
    echo '    export PYENV_ROOT="$HOME/.pyenv"' >> $1
    echo '    export PATH="$PYENV_ROOT/bin:$PATH"' >> $1
    echo '    eval "$(pyenv init --path)"' >> $1
    echo 'fi' >> $1
}

register_local_venv() {
    log_progress "Registering .local-venv to $1"
    echo 'if [ -f "${HOME}/.local-venv/bin/activate" ]' >> $1
    echo 'then' >> $1
    echo '    source "${HOME}/.local-venv/bin/activate"' >> $1
    echo 'fi' >> $1
}

if [ "$IS_TERMUX" = "1" ] && [ ! -d "$HOME/.local-venv" ]
then

    log_progress "Setting environment variables"
    export CFLAGS="-Wno-incompatible-function-pointer-types" # ruamel.yaml need this.
    # export CFLAGS="-Wno-incompatible-function-pointer-types -U__ANDROID_API__ -D__ANDROID_API__=26 -include unistd.h"
    # export GRPC_PYTHON_DISABLE_LIBC_COMPATIBILITY=1
    # export GRPC_PYTHON_BUILD_SYSTEM_OPENSSL=1 
    # export GRPC_PYTHON_BUILD_SYSTEM_ZLIB=1 
    # export GRPC_PYTHON_BUILD_SYSTEM_CARES=1 
    # export LDFLAGS="-llog"
    # export MATHLIB="m"

    log_progress "Change repo"
    termux-change-repo

    log_progress "Update existing packages"
    pkg update
    pkg upgrade -y

    if [ ! -d "${HOME}/storage" ]
    then
        log_progress "Setup storage"
        termux-setup-storage
    fi

    log_progress "Installing new packages"
    pkg install termux-api openssh curl wget git which \
        python rust clang cmake build-essential golang \
        binutils ninja patchelf libxml libxslt \
        postgresql sqlite

    log_progress "Creating local venv"
    python -m venv $HOME/.local-venv
    source $HOME/.local-venv/bin/activate

    
    # register local venv to .zshrc
    if command_exists zsh
    then
        register_local_venv "$HOME/.zshrc"
    fi

    # register local venv to .bashrc
    if command_exists bash
    then
        register_local_venv "$HOME/.bashrc"
    fi

elif [ "$IS_TERMUX" = "0" ]
then
    
    # Make sure pyenv is installed
    if [ ! -d "$HOME/.pyenv" ]
    then

        log_progress "Installing pyenv prerequisites"
        if [ "$os_type" = "darwin" ]
        then
            if command_exists brew
            then
                brew install openssl readline sqlite3 xz zlib tcl-tk
            else
                log_progress "Brew not found, continuing anyway"
            fi
        elif [ "$os_type" = "linux" ]
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
                try_sudo pacman -syu --noconfirm base-devel openssl zlib xz tk
            elif command_exists apk
            then
                try_sudo apk add --no-cache git bash build-base libffi-dev openssl-dev bzip2-dev zlib-dev xz-dev readline-dev sqlite-dev tk-dev
            else
                log_progress "No known package manager found, continuing anyway"
            fi
        else
            log_progress "Unsupported OS, cannot install pyenv pre-requisites, continuing anyway"
        fi

        log_progress "Installing pyenv"
        curl https://pyenv.run | bash

        # register .pyenv to .zshrc
        if [ -f "$HOME/.zshrc" ]
        then
            register_pyenv "$HOME/.zshrc"
        fi

        # register .pyenv to .bashrc
        if [ -f "$HOME/.bashrc" ]
        then
            register_pyenv "$HOME/.bashrc"
        fi

        # activate pyenv
        log_progress "Activating pyenv"
        export pyenv_root="$HOME/.pyenv"
        command -v pyenv >/dev/null || (export path="$pyenv_root/bin:$path" && eval "$(pyenv init -)")

        # install python 3.10.0
        log_progress "Installing python 3.10.0"
        pyenv install 3.10.0

        # set global python to 3.10.0
        log_progress "Setting python 3.10.0 as global"
        pyenv global 3.10.0
    fi
else
    log_progress "Assuming Python is installed"
fi

if ! command_exists poetry
then
    log_progress "Installing Poetry"
    pip install --upgrade pip setuptools
    pip install "poetry"
fi

if ! command_exists zrb
then
    log_progress "Installing Zrb"
    pip install zrb
fi
