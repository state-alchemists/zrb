set -e
if [ "{{ platform.system() }}" = "Darwin" ]
then
    sudo brew install zsh
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
    sudo apt install zsh
else
    echo "Cannot determine how to install zsh, assuming it has been installed"
fi

echo "Install oh-my-zsh"
sh -c "$(curl -fsSL https://raw.github.com/ohmyzsh/ohmyzsh/master/tools/install.sh)" "" --unattended

echo "Install zinit"
bash -c "$(curl -fsSL https://git.io/zinit-install)"