#!/bin/bash

PROJECT_DIR=$(pwd)
echo "🤖 Set project directory to ${PROJECT_DIR}"


_IS_EMPTY_VENV=0
if [ -z "$PROJECT_USE_VENV" ] || [ "$PROJECT_USE_VENV" = 1 ]
then
    if [ ! -d .venv ]
    then
        echo '🤖 Create virtual environment'
        python -m venv "${PROJECT_DIR}/.venv"
        _IS_EMPTY_VENV=1
    fi
    echo '🤖 Activate virtual environment'
    source "${PROJECT_DIR}/.venv/bin/activate"
fi

install_requirements() {
    echo '🤖 Install requirements'
    pip install --upgrade pip
    pip install -r "${PROJECT_DIR}/requirements.txt"
}

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
        if [ "$_IS_EMPTY_VENV" = 1 ]
        then
            install_requirements
            _IS_EMPTY_VENV=0
        else
            echo '🤖 Checking .venv and requirements.txt timestamp'
            _VENV_TIMESTAMP=$(find .venv -type d -exec stat -c %Y {} \; | sort -n | tail -n 1)
            _REQUIREMENTS_TIMESTAMP=$(stat -c %Y requirements.txt)
            if [ "$_VENV_TIMESTAMP" -lt "$_REQUIREMENTS_TIMESTAMP" ] 
            then
                install_requirements
            fi
        fi
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
        echo "🤖 Set up shell completion for $_CURRENT_SHELL"
        eval "$(_ZRB_COMPLETE=${_CURRENT_SHELL}_source zrb)"
    else
        echo "🤖 Cannot set up shell completion for $_CURRENT_SHELL"
    fi
}

reload
echo '🤖 Happy Coding :)'
