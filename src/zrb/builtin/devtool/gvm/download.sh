if [ ! -d "${HOME}/.gvm" ]
then
    echo "Download GVM"
    curl -o- https://raw.githubusercontent.com/moovweb/gvm/master/binscripts/gvm-installer | bash
else
    echo "GVM already exists"
fi