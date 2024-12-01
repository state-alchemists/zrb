#!/bin/bash

if [ -n "$PREFIX" ] && [ "$PREFIX" = "/data/data/com.termux/files/usr" ]
then
    _IS_TERMUX=1
else
    _IS_TERMUX=0
fi


log_info() {
    echo -e "🤖 \e[0;33m${1}\e[0;0m"
}


command_exists() {
    command -v "$1" &> /dev/null
}


init() {
    export PROJECT_DIR=$(pwd)
    export ZRB_INIT_SCRIPTS=""
    export ZRB_INIT_MODULES=""
    log_info "Setting project directory to ${PROJECT_DIR}"
    if ! command_exists poetry
    then
        log_info 'Install poetry'
        pip install --upgrade pip setuptools
        pip install "poetry"
    fi
    if [ ! -d "${PROJECT_DIR}/.venv" ]
    then
        log_info 'Creating virtual environment'
        python -m venv "${PROJECT_DIR}/.venv"
    fi
    log_info 'Activating virtual environment'
    source "${PROJECT_DIR}/.venv/bin/activate"
}


reload() {

    if [ ! -f "${PROJECT_DIR}/.env" ]
    then
        log_info 'Creating project configuration (.env)'
        cp "${PROJECT_DIR}/template.env" "${PROJECT_DIR}/.env"
    fi

    log_info 'Loading project configuration (.env)'
    source "${PROJECT_DIR}/.env"

    if [ "$_IS_TERMUX" = "1" ]
    then
        log_info 'Updating Build Flags'
        _OLD_CFLAGS="$CFLAGS"
        GRPC_PYTHON_DISABLE_LIBC_COMPATIBILITY=1
        GRPC_PYTHON_BUILD_SYSTEM_OPENSSL=1
        GRPC_PYTHON_BUILD_SYSTEM_ZLIB=1
        GRPC_PYTHON_BUILD_SYSTEM_CARES=1
        CFLAGS+=" -U__ANDROID_API__ -D__ANDROID_API__=30 -include unistd.h -Wno-incompatible-function-pointer-types"
        LDFLAGS+=" -llog"
        # export CFLAGS="$_OLD_CFLAGS -Wno-incompatible-function-pointer-types" # ruamel.yaml need this.
    fi

    log_info 'Install'
    poetry check && poetry install -E rag --no-root

    if [ "$_IS_TERMUX" = "1" ]
    then
        log_info 'Restoring Build Flags'
        export CFLAGS="$_OLD_CFLAGS"
    fi

    case $(ps -p $$ | awk 'NR==2 {print $4}') in
    *zsh)
        log_info "Setting up shell completion for zsh"
        source <(zrb shell autocomplete zsh)
        ;;
    *bash)
        log_info "Setting up shell completion for bash"
        source <(zrb shell autocomplete bash)
        ;;
    esac
}

init
reload
log_info 'Happy Coding :)'
