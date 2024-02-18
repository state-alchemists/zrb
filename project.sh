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
        _IS_EMPTY_VENV=1
    fi

    log_progress 'Activating virtual environment'
    source "${PROJECT_DIR}/.venv/bin/activate"
}


install_requirements() {
    log_progress "Installing requirements from $1"
    pip install --upgrade pip
    pip install -r "$1"
}


reload() {

    if [ ! -f "${PROJECT_DIR}/.env" ]
    then
        log_progress 'Creating project configuration (.env)'
        cp "${PROJECT_DIR}/template.env" "${PROJECT_DIR}/.env"
    fi

    log_progress 'Loading project configuration (.env)'
    source "${PROJECT_DIR}/.env"

    if [ -z "$PROJECT_AUTO_INSTALL_PIP" ] || [ "$PROJECT_AUTO_INSTALL_PIP" = 1 ] || [ "$_IS_EMPTY_VENV" = 1 ]
    then
        if [ "$_IS_EMPTY_VENV" = 1 ]
        then
            install_requirements "${PROJECT_DIR}/requirements.txt"
            install_requirements "${PROJECT_DIR}/requirements-dev.txt"
            _IS_EMPTY_VENV=0
        else
            log_progress 'Checking .venv and modification time'
            _VENV_MTIME=$(find .venv -type d -exec stat -c %Y {} \; | sort -n | tail -n 1)
            log_progress 'Checking requirements.txt modification time'
            _REQUIREMENTS_MTIME=$(stat -c %Y requirements.txt)
            if [ "$_VENV_MTIME" -lt "$_REQUIREMENTS_MTIME" ] 
            then
                install_requirements "${PROJECT_DIR}/requirements.txt"
            fi
            log_progress 'Checking requirements-dev.txt modification time'
            REQUIREMENTS_DEV_MTIME=$(stat -c %Y requirements-dev.txt)
            if [ "$_VENV_MTIME" -lt "$REQUIREMENTS_DEV_MTIME" ] 
            then
                install_requirements "${PROJECT_DIR}/requirements-dev.txt"
            fi
        fi
    fi

    log_progress 'Installing Zrb as symlink'
    flit install --symlink

    _CURRENT_SHELL=$(ps -p $$ | awk 'NR==2 {print $4}')
    case "$_CURRENT_SHELL" in
    *zsh)
        _CURRENT_SHELL="zsh"
        ;;
    *bash)
        _CURRENT_SHELL="bash"
        ;;
    esac
    _CURRENT_SHELL=$(ps -p $$ | awk 'NR==2 {print $4}')
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
