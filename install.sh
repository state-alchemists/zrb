set -e

# Make sure pyenv is installed
if [ ! -d "$HOME/.pyenv" ]
then
    echo "Installing Pyenv"
    curl https://pyenv.run | bash

    # Register .pyenv to .zshrc
    if [ -f "$HOME/.zshrc" ]
    then
        echo "Registering Pyenv to .zshrc"
        echo '' >> $HOME/.zshrc
        echo 'export PYENV_ROOT="$HOME/.pyenv"' >> $HOME/.zshrc
        echo 'command -v pyenv >/dev/null || export PATH="$PYENV_ROOT/bin:$PATH"' >> $HOME/.zshrc
        echo 'eval "$(pyenv init -)"' >> $HOME/.zshrc
    fi

    # Register .pyenv to .bashrc
    if [ -f "$HOME/.bashrc" ]
    then
        echo "Registering Pyenv to .bashrc"
        echo '' >> $HOME/.bashrc
        echo 'export PYENV_ROOT="$HOME/.pyenv"' >> $HOME/.bashrc
        echo 'command -v pyenv >/dev/null || export PATH="$PYENV_ROOT/bin:$PATH"' >> $HOME/.bashrc
        echo 'eval "$(pyenv init -)"' >> $HOME/.bashrc
    fi

    # Activate pyenv
    echo "Activating pyenv"
    export PYENV_ROOT="$HOME/.pyenv"
    command -v pyenv >/dev/null || (export PATH="$PYENV_ROOT/bin:$PATH" && eval "$(pyenv init -)")

    # Install python 3.10.0
    echo "Installing python 3.10.0"
    pyenv install 3.10.0

    # Set global python to 3.10.0
    echo "Set python 3.10.0 as global"
    pyenv global 3.10.0
fi

echo "Installing Zrb"
pip install zrb