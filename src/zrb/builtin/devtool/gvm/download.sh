set -e
if [ ! -d "${HOME}/.gvm" ]
then
    set +e
    which apt
    if [ "$?" = 0 ]
    then
        sudo apt install bison
    fi
    set -e
    echo "Download GVM"
    curl -o- https://raw.githubusercontent.com/moovweb/gvm/master/binscripts/gvm-installer | bash
else
    echo "GVM already exists under ${HOME}/.gvm"
fi