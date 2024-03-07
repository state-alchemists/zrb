set -e
if [ -f './terraform.zip' ]
then
    log_info 'terraform.zip already downloaded'
else
    curl "https://releases.hashicorp.com/terraform/1.0.9/terraform_1.0.9_linux_amd64.zip" -o "terraform.zip"
fi

unzip terraform.zip
mkdir -p "${HOME}/.terraform"
mv terraform "${HOME}/.terraform/terraform"
