set -e

# Function to check if a command exists
command_exists() {
    command -v "$1" &> /dev/null
}

if [ ! -d "${HOME}/.gvm" ]
then
    if command_exists apt
    then
        sudo apt install -y bison
    fi
    echo "Download GVM"
    curl -o- https://raw.githubusercontent.com/moovweb/gvm/master/binscripts/gvm-installer | bash
else
    echo "GVM already exists under ${HOME}/.gvm"
fi