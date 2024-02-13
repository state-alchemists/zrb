if [ "$OS_TYPE" = "Linux" ]
then
    if command_exists pkg
    then
        try_sudo pkg update
        try_sudo pkg install -y unzip wget
    elif command_exists apt
    then
        try_sudo apt install -y unzip wget
    else
        echo "apt does not exists"
        exit 1
    fi 

    if command_exists dpkg
    then
        wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
        try_sudo dpkg -i google-chrome-stable_current_amd64.deb
    else
        echo "dpkg does not exists"
        exit 1
    fi

    try_sudo apt --fix-broken install
else
    echo "Unsupported OS type. Please install zsh manually."
    exit 1
fi

echo "Get latest chrome driver version"
chrome_driver=$(curl "https://chromedriver.storage.googleapis.com/LATEST_RELEASE")
echo "$chrome_driver"

echo "Download chrome driver"
curl -Lo chromedriver_linux64.zip "https://chromedriver.storage.googleapis.com/${chrome_driver}/chromedriver_linux64.zip"

echo "Install chrome driver"
rm -Rf "${HOME}/chromedriver/stable"
mkdir -p "${HOME}/chromedriver/stable"
unzip -q "chromedriver_linux64.zip" -d "${HOME}/chromedriver/stable"
chmod +x "${HOME}/chromedriver/stable/chromedriver"

echo "Install selenium"
pip install selenium