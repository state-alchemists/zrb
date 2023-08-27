set -e
if [ ! -f "./awscliv2.zip" ]
then
    echo "Download AWS CLI"
    curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
else
    echo "AWS CLI already downloaded"
fi

set +e
which apt
if [ "$?" = 0 ]
then
    sudo apt install -y unzip
fi
set -e 

if [ ! -d "./aws" ]
then
    echo "Unzip AWS CLI"
    unzip awscliv2.zip
fi
echo "Install AWS CLI"
sudo ./aws/install --update
