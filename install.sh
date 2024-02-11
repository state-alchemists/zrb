set -e
OS_TYPE=$(uname)

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

# Make sure pyenv is installed
if [ ! -d "$HOME/.pyenv" ]
then

    echo "Installing Pyenv prerequisites"
    if [ "$OS_TYPE" = "Darwin" ]
    then
        if command_exists brew
        then
            brew install openssl readline sqlite3 xz zlib tcl-tk
        else
            echo "Brew not found, continuing anyway"
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
            echo "No known package manager found, continuing anyway"
        fi
    else
        echo "Unknown OS, cannot install pre-requisites, continuing anyway"
    fi

    echo "Installing Pyenv"
    curl https://pyenv.run | bash

    # Register .pyenv to .zshrc
    if [ -f "$HOME/.zshrc" ]
    then
        echo "Registering Pyenv to .zshrc"
        echo '' >> $HOME/.zshrc
        echo 'export PYENV_ROOT="$HOME/.pyenv"' >> $HOME/.zshrc
        echo 'command -v pyenv >/dev/null || export PATH="$PYENV_ROOT/bin:$PATH"' >> $HOME/.zshrc
        echo 'eval "$(pyenv init -)"' >> $HOME/.zshrc
    fi

    # Register .pyenv to .bashrc
    if [ -f "$HOME/.bashrc" ]
    then
        echo "Registering Pyenv to .bashrc"
        echo '' >> $HOME/.bashrc
        echo 'export PYENV_ROOT="$HOME/.pyenv"' >> $HOME/.bashrc
        echo 'command -v pyenv >/dev/null || export PATH="$PYENV_ROOT/bin:$PATH"' >> $HOME/.bashrc
        echo 'eval "$(pyenv init -)"' >> $HOME/.bashrc
    fi

    # Activate pyenv
    echo "Activating pyenv"
    export PYENV_ROOT="$HOME/.pyenv"
    command -v pyenv >/dev/null || (export PATH="$PYENV_ROOT/bin:$PATH" && eval "$(pyenv init -)")

    # Install python 3.10.0
    echo "Installing python 3.10.0"
    pyenv install 3.10.0

    # Set global python to 3.10.0
    echo "Set python 3.10.0 as global"
    pyenv global 3.10.0
fi

echo "Installing Zrb"
pip install zrb