if [ ! -d "${HOME}/.pulumi" ]
then
    echo "Download Pulumi"
    curl -fsSL https://get.pulumi.com | bash
else
    echo "Pulumi already exists"
fi