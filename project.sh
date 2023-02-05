#!/bin/bash
set -e

if [ -z "$PROJECT_DIR" ]
then
    export PROJECT_DIR=$(pwd)
    echo "🤖 Setting project directory to ${PROJECT_DIR}"
fi

if [ ! -d venv ]
then
    echo '🤖 Creating virtual environment'
    python -m venv "${PROJECT_DIR}/venv"
    echo '🤖 Activating virtual environment'
    source "${PROJECT_DIR}/venv/bin/activate"
    echo '🤖 Installing requirements'
    pip install --upgrade pip
    pip install -r "${PROJECT_DIR}/requirements.txt"
fi

echo '🤖 Activating virtual environment'
source "${PROJECT_DIR}/venv/bin/activate"

reload() {
    if [ ! -z "$PROJECT_AUTO_INSTALL_PIP" ] && [[ "$PROJECT_AUTO_INSTALL_PIP" == 1 ]]
    then
        echo '🤖 Installing requirements'
        pip install --upgrade pip
        pip install -r "${PROJECT_DIR}/requirements.txt"
    fi
    echo '🤖 Installing zrb as symlink'
    flit install --symlink
    if [ ! -f "${PROJECT_DIR}/.env" ]
    then
        echo '🤖 Creating project configuration (.env)'
        cp "${PROJECT_DIR}/template.env" "${PROJECT_DIR}/.env"
    fi
    echo '🤖 Load project configuration (.env)'
    source "${PROJECT_DIR}/.env"
}

reload
echo '🤖 Happy Coding :)'
