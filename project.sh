#!/bin/bash

log_progress() {
    echo -e "🤖 \e[0;33m${1}\e[0;0m"
}


init() {
    export PROJECT_DIR=$(pwd)
    log_progress "Setting project directory to ${PROJECT_DIR}"

    _IS_EMPTY_VENV=0
    if [ ! -d "${PROJECT_DIR}/.venv" ]
    then
        log_progress 'Creating virtual environment'
        python -m venv "${PROJECT_DIR}/.venv"
        source "${PROJECT_DIR}/.venv/bin/activate"
        pip install --upgrade pip
        pip install "poetry==1.7.1"
        _IS_EMPTY_VENV=1
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

    log_progress 'Install'
    poetry install

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
