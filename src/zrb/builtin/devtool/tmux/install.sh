set -e
if [ "{{ platform.system() }}" = "Darwin" ]
then
    sudo brew install tmux
elif [ "{{ platform.system() }}" = "Linux" ]
then
    sudo apt install tmux
else
    echo "Cannot determine how to install tmux, assuming it has been installed"
fi