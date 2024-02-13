if [ ! -d "${HOME}/.gvm" ]
then
    if command_exists pkg
    then
        try_sudo pkg update
        try_sudo pkg install -y bison ncurses-utils
    elif command_exists apt
    then
        try_sudo apt install -y bison
    fi
    echo "Download GVM"
    curl -o- https://raw.githubusercontent.com/moovweb/gvm/master/binscripts/gvm-installer | bash
else
    echo "GVM already exists under ${HOME}/.gvm"
fi