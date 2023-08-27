set -e
if [ "{{ platform.system() }}" = "Darwin" ]
then
    sudo brew install tmux
elif [ "{{ platform.system() }}" = "Linux" ]
then
    set +e
    which apt
    if [ "$?" != 0 ]
    then
        >&2 echo "apt not found"
        exit 1
    fi
    set -e
    sudo apt install -y tmux
else
    echo "Cannot determine how to install tmux, assuming it has been installed"
fi