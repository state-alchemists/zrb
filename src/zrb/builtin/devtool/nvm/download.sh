if [ ! -d "${HOME}/.nvm" ]
then
    echo "Download nvm"
    curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.3/install.sh | bash
else
    echo "Nvm already exists"
fi