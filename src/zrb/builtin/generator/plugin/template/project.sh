#!/bin/bash

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


init() {
    export PROJECT_DIR=$(pwd)
    log_progress "Setting project directory to ${PROJECT_DIR}"
    if ! command_exists poetry
    then
        log_progress 'Install poetry'
        pip install --upgrade pip setuptools
        pip install "poetry"
    fi
    if [ ! -d "${PROJECT_DIR}/.venv" ]
    then
        log_progress 'Creating virtual environment'
        python -m venv "${PROJECT_DIR}/.venv"
    fi
    log_progress 'Activating virtual environment'
    source "${PROJECT_DIR}/.venv/bin/activate"
}


reload() {

    if [ ! -f "${PROJECT_DIR}/.env" ]
    then
        log_progress 'Creating project configuration (.env)'
        cp "${PROJECT_DIR}/template.env" "${PROJECT_DIR}/.env"
    fi

    log_progress 'Loading project configuration (.env)'
    source "${PROJECT_DIR}/.env"

    if [ "$IS_TERMUX" = "1" ]
    then
        log_progress 'Updating Build Flags'
        _OLD_CFLAGS="$CFLAGS"
        export CFLAGS="$_OLD_CFLAGS -Wno-incompatible-function-pointer-types" # ruamel.yaml need this.
    fi

    log_progress 'Install'
    poetry install

    if [ "$IS_TERMUX" = "1" ]
    then
        log_progress 'Restoring Build Flags'
        export CFLAGS="$_OLD_CFLAGS"
    fi

    _CURRENT_SHELL=$(ps -p $$ | awk 'NR==2 {print $4}')
    case "$_CURRENT_SHELL" in
    *zsh)
        _CURRENT_SHELL="zsh"
        ;;
    *bash)
        _CURRENT_SHELL="bash"
        ;;
    esac
    if [ "$_CURRENT_SHELL" = "zsh" ] || [ "$_CURRENT_SHELL" = "bash" ]
    then
        log_progress "Setting up shell completion for $_CURRENT_SHELL"
        eval "$(_ZRB_COMPLETE=${_CURRENT_SHELL}_source zrb)"
    else
        log_progress "Cannot set up shell completion for $_CURRENT_SHELL"
    fi
}

init
reload
log_progress 'Happy Coding :)'
