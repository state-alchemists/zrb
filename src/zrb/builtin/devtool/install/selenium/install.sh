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
        log_info "apt does not exists"
        exit 1
    fi 

    if command_exists dpkg
    then
        set +e
        wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
        try_sudo dpkg -i google-chrome-stable_current_amd64.deb
        set -e
    else
        log_info "dpkg does not exists"
        exit 1
    fi

    if command_exists apt
    then
        try_sudo apt --fix-broken install -y
    fi
else
    log_info "Unsupported OS type. Please install zsh manually."
    exit 1
fi

log_info "Get latest chrome driver version"
chrome_driver=$(curl "https://chromedriver.storage.googleapis.com/LATEST_RELEASE")
log_info "$chrome_driver"

log_info "Download chrome driver"
curl -Lo chromedriver_linux64.zip "https://chromedriver.storage.googleapis.com/${chrome_driver}/chromedriver_linux64.zip"

log_info "Install chrome driver"
rm -Rf "${HOME}/chromedriver/stable"
mkdir -p "${HOME}/chromedriver/stable"
unzip -q "chromedriver_linux64.zip" -d "${HOME}/chromedriver/stable"
chmod +x "${HOME}/chromedriver/stable/chromedriver"

log_info "Install selenium"
pip install selenium