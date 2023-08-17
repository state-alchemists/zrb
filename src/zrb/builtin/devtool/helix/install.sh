set -e
if [ "{{ platform.system() }}" = "Darwin" ]
then
    sudo brew install helix
elif [ "{{ platform.system() }}" = "Linux" ]
then
    set +e
    apt --version
    if [ "$?" != 0 ]
    then
        >&2 echo "apt not found"
        exit 1
    fi
    set -e
    sudo add-apt-repository ppa:maveonair/helix-editor -y
    sudo apt update
    sudo apt install helix
else
    echo "Cannot determine how to install zsh, assuming it has been installed"
fi