__CURRENT_DIR=$(pwd)

__prepare() {
    cd $__CURRENT_DIR
    source venv/bin/activate
}

prepare() {
    __prepare
    pip install -r requirements.txt
}

build-zrb() {
    prepare
    rm -Rf dist
    python -m build
}

upload-zrb() {
    prepare
    python -m twine upload --repository pypi dist/*
}

test-upload-zrb() {
    prepare
    python -m twine upload --repository testpypi dist/*
}

prepare-playground() {
    echo "Build zrb"
    build-zrb
    if [ ! -d playground ]
    then
        echo "Create playground"
        cp -r playground-template playground
    fi
    echo "Copy zrb wheel file"
    cp dist/zrb-*.whl playground/zrb-0.0.1-py3-none-any.whl
    cd playground
    deactivate
    echo "Activate playground venv"
    python -m venv venv
    source venv/bin/activate
    echo "Install requirements"
    pip install -r requirements.txt
    echo "Install zrb"
    pip install zrb-0.0.1-py3-none-any.whl --no-deps
    echo "Deactivate playground venv"
    deactivate
    cd $__CURRENT_DIR
    __prepare
}

reset-playground() {
    echo "Remove playground"
    rm -Rf playground
    prepare-playground
}


cheat-sheet() {
    echo "Available commands:"
    echo "- prepare"
    echo "- build-zrb"
    echo "- upload-zrb"
    echo "- test-upload-zrb"
    echo "- prepare-playground"
    echo "- reset-playground"
}
cheat-sheet