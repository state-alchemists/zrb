#!/bin/bash

export PROJECT_DIR=$(pwd)
echo "🤖 Set project directory to ${PROJECT_DIR}"

if [ ! -d "${PROJECT_DIR}/.venv" ]
then
    echo '🤖 Create virtual environment'
    python -m venv "${PROJECT_DIR}/.venv"
fi

echo '🤖 Activate virtual environment'
source "${PROJECT_DIR}/.venv/bin/activate"

reload() {

    if [ ! -f "${PROJECT_DIR}/.env" ]
    then
        echo '🤖 Create project configuration (.env)'
        cp "${PROJECT_DIR}/template.env" "${PROJECT_DIR}/.env"
    fi

    echo '🤖 Load project configuration (.env)'
    source "${PROJECT_DIR}/.env"

    if [ -z "$PROJECT_AUTO_INSTALL_PIP" ] || [ "$PROJECT_AUTO_INSTALL_PIP" = 1 ]
    then
        echo '🤖 Install requirements'
        pip install --upgrade pip
        pip install -r "${PROJECT_DIR}/requirements.txt"
    fi

    echo '🤖 Install zrb as symlink'
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
        echo "🤖 Set up shell completion for $_CURRENT_SHELL"
        eval "$(_ZRB_COMPLETE=${_CURRENT_SHELL}_source zrb)"
    else
        echo "🤖 Cannot set up shell completion for $_CURRENT_SHELL"
    fi
}

reload
echo '🤖 Happy Coding :)'
