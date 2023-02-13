if [ ! -d "${HOME}/.pyenv" ]
then
    echo "Download Pyenv"
    curl https://pyenv.run | bash
else
    echo "Pyenv already exists"
fi