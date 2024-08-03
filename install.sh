set -e
OS_TYPE=$(uname)

if [ -n "$PREFIX" ] && [ "$PREFIX" = "/data/data/com.termux/files/usr" ]
then
    IS_TERMUX=1
else
    IS_TERMUX=0
fi

log_info() {
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
    log_info "Registering Pyenv to $1"
    echo 'if [ -d "${HOME}/.pyenv" ]' >> $1
    echo 'then' >> $1
    echo '    export PYENV_ROOT="$HOME/.pyenv"' >> $1
    echo '    export PATH="$PYENV_ROOT/bin:$PATH"' >> $1
    echo '    eval "$(pyenv init --path)"' >> $1
    echo 'fi' >> $1
}

register_local_venv() {
    log_info "Registering .local-venv to $1"
    echo 'if [ -f "${HOME}/.local-venv/bin/activate" ]' >> $1
    echo 'then' >> $1
    echo '    source "${HOME}/.local-venv/bin/activate"' >> $1
    echo 'fi' >> $1
}

if [ "$IS_TERMUX" = "1" ] && [ ! -d "$HOME/.local-venv" ]
then

    log_info "Setting environment variables"
    export CFLAGS="-Wno-incompatible-function-pointer-types" # ruamel.yaml need this.

    log_info "Change repo"
    termux-change-repo

    log_info "Update existing packages"
    pkg update
    pkg upgrade -y

    if [ ! -d "${HOME}/storage" ]
    then
        log_info "Setup storage"
        termux-setup-storage
    fi

    log_info "Installing new packages"
    pkg install termux-api openssh curl wget git which \
        python rust clang cmake build-essential golang swig \
        binutils ninja patchelf libxml2 libxslt \
        postgresql sqlite

    log_info "Creating local venv"
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

        if [ "$OS_TYPE" = "darwin" ]
        then
            if command_exists brew
            then
                log_info "Using brew to install pyenv prerequisites"
                brew install openssl readline sqlite3 xz zlib tcl-tk
            else
                log_info "Brew not found, continuing anyway"
            fi
        elif [ "$OS_TYPE" = "linux" ]
        then
            if command_exists pkg
            then
                log_info "Using pkg to install pyenv prerequisites"
                try_sudo pkg update
                try_sudo pkg install -y build-essential
            elif command_exists apt
            then
                log_info "Using apt to install pyenv prerequisites"
                try_sudo apt update
                try_sudo apt install -y build-essential libssl-dev zlib1g-dev \
                    libbz2-dev libreadline-dev libsqlite3-dev curl \
                    libncursesw5-dev xz-utils tk-dev libxml2-dev libxmlsec1-dev libffi-dev liblzma-dev
            elif command_exists yum
            then
                log_info "Using yum to install pyenv prerequisites"
                try_sudo yum install -y gcc make patch zlib-devel bzip2 bzip2-devel readline-devel sqlite sqlite-devel openssl-devel tk-devel libffi-devel xz-devel
            elif command_exists dnf
            then
                log_info "Using dnf to install pyenv prerequisites"
                try_sudo dnf install -y make gcc patch zlib-devel bzip2 bzip2-devel readline-devel sqlite sqlite-devel openssl-devel tk-devel libffi-devel xz-devel libuuid-devel gdbm-libs libnsl2
            elif command_exists pacman
            then
                log_info "Using pacman to install pyenv prerequisites"
                try_sudo pacman -syu --noconfirm base-devel openssl zlib xz tk
            elif command_exists apk
            then
                log_info "Using apk to install pyenv prerequisites"
                try_sudo apk add --no-cache git bash build-base libffi-dev openssl-dev bzip2-dev zlib-dev xz-dev readline-dev sqlite-dev tk-dev
            else
                log_info "No known package manager found, continuing anyway"
            fi
        else
            log_info "Unsupported OS, cannot install pyenv pre-requisites, continuing anyway"
        fi
        log_info "Installing pyenv"
        curl https://pyenv.run | bash
    fi

    if ! command_exists pyenv
    then
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
        log_info "Activating pyenv"
        export PYENV_ROOT="$HOME/.pyenv"
        export PATH="$PYENV_ROOT/bin:$PATH"
        eval "$(pyenv init -)"
        eval "$(pyenv virtualenv-init -)"
    fi

    if ! command_exists python
    then
        # install python 3.10.0
        log_info "Installing python 3.10.0"
        pyenv install 3.10.0
        # set global python to 3.10.0
        log_info "Setting python 3.10.0 as global"
        pyenv global 3.10.0
    fi
else
    log_info "Assuming Python is installed"
fi

if ! command_exists poetry
then
    log_info "Installing Poetry"
    pip install --upgrade pip setuptools
    pip install poetry
fi

if ! command_exists zrb
then
    log_info "Installing Zrb"
    eval pip install zrb
fi
