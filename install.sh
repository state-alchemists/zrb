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

register_pyenv() {
    echo "Registering Pyenv to $1"
    echo '' >> $1
    echo 'export pyenv_root="$HOME/.pyenv"' >> $1
    echo 'command -v pyenv >/dev/null || export PATH="$PYENV_ROOT/bin:$PATH"' >> $1
    echo 'eval "$(pyenv init -)"' >> $1
}

register_local_venv() {
    echo "Registering .local venv to $1"
    echo '' >> $1
    echo 'export CFLAGS="-wno-incompatible-function-pointer-types"' >> $1
    echo 'export GRPC_PYTHON_DISABLE_LIBC_COMPATIBILITY=1' >> $1
    echo 'export GRPC_PYTHON_BUILD_SYSTEM_OPENSSL=1 ' >> $1
    echo 'export GRPC_PYTHON_BUILD_SYSTEM_ZLIB=1 ' >> $1
    echo 'export GRPC_PYTHON_BUILD_SYSTEM_CARES=1 ' >> $1
    echo 'export CFLAGS="$CFLAGS -u__android_api__ -d__android_api__=26 -include unistd.h"' >> $1
    echo 'export LDFLAGS="$LDFLAGS -llog"' >> $1
    echo 'export MATHLIB="m"' >> $1
    echo 'source $HOME/.local/bin/activate' >> $1
}

if [[ -n "$PREFIX" ]] && [[ "$PREFIX" == "/data/data/com.termux/files/usr" ]]; then

    export CFLAGS="-wno-incompatible-function-pointer-types"
    export GRPC_PYTHON_DISABLE_LIBC_COMPATIBILITY=1
    export GRPC_PYTHON_BUILD_SYSTEM_OPENSSL=1 
    export GRPC_PYTHON_BUILD_SYSTEM_ZLIB=1 
    export GRPC_PYTHON_BUILD_SYSTEM_CARES=1 
    export CFLAGS="$CFLAGS -u__android_api__ -d__android_api__=26 -include unistd.h"
    export LDFLAGS="$LDFLAGS -llog"
    export MATHLIB="m"

    pkg install python rust clang cmake build-essential golang git openssh tmux helix curl wget binutils postgresql sqlite

    python -m venv $HOME/.local
    source $HOME/.local/bin/activate

    
    # register local venv to .zshrc
    if [ -f "$HOME/.zshrc" ]
    then
        register_local_venv "$HOME/.zshrc"
    fi

    # register local venv to .bashrc
    if [ -f "$HOME/.bashrc" ]
    then
        register_local_venv "$HOME/.bashrc"
    fi

else

    # Make sure pyenv is installed
    if [ ! -d "$HOME/.pyenv" ]
    then

        echo "installing pyenv prerequisites"
        if [ "$os_type" = "darwin" ]
        then
            if command_exists brew
            then
                brew install openssl readline sqlite3 xz zlib tcl-tk
            else
                echo "brew not found, continuing anyway"
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
                echo "no known package manager found, continuing anyway"
            fi
        else
            echo "unknown package manager, cannot install pyenv pre-requisites, continuing anyway"
        fi

        echo "installing pyenv"
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
        echo "activating pyenv"
        export pyenv_root="$HOME/.pyenv"
        command -v pyenv >/dev/null || (export path="$pyenv_root/bin:$path" && eval "$(pyenv init -)")

        # install python 3.10.0
        echo "installing python 3.10.0"
        pyenv install 3.10.0

        # set global python to 3.10.0
        echo "set python 3.10.0 as global"
        pyenv global 3.10.0
    fi

fi

echo "Installing Zrb"
pip install zrb
