set -e
if [ ! -f "./awscliv2.zip" ]
then
    echo "Download AWS CLI"
    curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
else
    echo "AWS CLI already downloaded"
fi