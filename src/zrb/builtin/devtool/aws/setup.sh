set -e
if [ ! -d "./aws" ]
then
    echo "Unzip AWS CLI"
    unzip awscliv2.zip
fi
echo "Install AWS CLI"
sudo ./aws/install --update
