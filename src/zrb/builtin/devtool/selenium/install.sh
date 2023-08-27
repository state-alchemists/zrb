set -e
wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb

set +e
which dpkg
if [ "$?" = 0 ]
then
    sudo dpkg -i google-chrome-stable_current_amd64.deb
fi

which apt
if [ "$?" = 0 ]
then
    sudo apt --fix-broken install
    sudo apt install unzip
fi
set -e

echo "Get latest chrome driver version"
chrome_driver=$(curl "https://chromedriver.storage.googleapis.com/LATEST_RELEASE")
echo "$chrome_driver"

echo "Download chrome driver"
curl -Lo chromedriver_linux64.zip "https://chromedriver.storage.googleapis.com/${chrome_driver}/chromedriver_linux64.zip"

echo "Install chrome driver"
mkdir -p "${HOME}/chromedriver/stable"
unzip -q "chromedriver_linux64.zip" -d "${HOME}/chromedriver/stable"
chmod +x "${HOME}/chromedriver/stable/chromedriver"

echo "Install selenium"
pip install selenium