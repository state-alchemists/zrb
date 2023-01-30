if [ -z "$__PROJECT_DIR" ]
then
    __PROJECT_DIR=$(pwd)
fi

__prepare() {
    echo "🤖 Activate zrb venv"
    source ${__PROJECT_DIR}/venv/bin/activate
}

reload-toolkit() {
    source ${__PROJECT_DIR}/toolkit.sh
}

prepare() {
    __prepare
    echo "🤖 Upgrade pip"
    pip install --upgrade pip
    echo "🤖 Install zrb dependencies"
    pip install -r ${__PROJECT_DIR}/requirements.txt
}

build-zrb() {
    prepare
    echo "🤖 Build zrb distribution"
    rm -Rf ${__PROJECT_DIR}/dist
    cd ${__PROJECT_DIR}
    git add . -A
    flit build
}

publish-zrb() {
    prepare
    echo "🤖 Publish zrb to pypi"
    cd ${__PROJECT_DIR}
    flit publish --repository pypi
}

test-publish-zrb() {
    prepare
    echo "🤖 Publish zrb to testpypi"
    cd ${__PROJECT_DIR}
    flit publish --repository testpypi
}

prepare-playground() {
    build-zrb
    if [ ! -d playground ]
    then
        echo "🤖 Create playground"
        cp -r ${__PROJECT_DIR}/playground-template ${__PROJECT_DIR}/playground
    fi
    echo "🤖 Copy zrb distribution"
    cp ${__PROJECT_DIR}/dist/zrb-*.tar.gz ${__PROJECT_DIR}/playground/zrb-0.0.1-py3-none-any.tar.gz
    cd ${__PROJECT_DIR}/playground
    deactivate
    echo "🤖 Activate playground venv"
    python -m venv venv
    source venv/bin/activate
    echo "🤖 Upgrade pip"
    pip install --upgrade pip
    echo "🤖 Install playground dependencies"
    pip install -r requirements.txt
    echo "🤖 Install zrb into playground"
    pip install zrb-0.0.1-py3-none-any.tar.gz
    echo "🤖 Deactivate playground venv"
    deactivate
    cd ${__PROJECT_DIR}
    __prepare
}

reset-playground() {
    echo "🤖 Remove playground"
    rm -Rf ${__PROJECT_DIR}/playground
    prepare-playground
}

play() {
    __prepare
    echo "🤖 Deactivate zrb venv"
    deactivate
    cd ${__PROJECT_DIR}/playground
    echo "🤖 Activate playground venv"
    source ${__PROJECT_DIR}/playground/venv/bin/activate
}


cheat-sheet() {
    echo "Available commands:"
    echo "- reload-tookit"
    echo "- prepare"
    echo "- build-zrb"
    echo "- publish-zrb"
    echo "- test-publish-zrb"
    echo "- prepare-playground"
    echo "- reset-playground"
    echo "- play"
}
cheat-sheet