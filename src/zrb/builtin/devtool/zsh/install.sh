set -e
if [ "{{ platform.system() }}" = "Darwin" ]
then
    sudo brew install zsh
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
    sudo apt install -y zsh
else
    echo "Cannot determine how to install zsh, assuming it has been installed"
fi

set +e
which chsh
if [ "$?" = 0 ]
then
    set -e
    echo "Change default shell to zsh"
    sudo chsh -s $(which zsh)
fi
set -e

echo "Install oh-my-zsh"
sh -c "$(curl -fsSL https://raw.github.com/ohmyzsh/ohmyzsh/master/tools/install.sh)" "" --unattended

echo "Install zinit"
bash -c "$(curl -fsSL https://git.io/zinit-install)"