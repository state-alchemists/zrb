set -e
if [ ! -d "${HOME}/.pulumi" ]
then
    log_info "Download Pulumi"
    curl -fsSL https://get.pulumi.com | bash
else
    log_info "Pulumi already exists"
fi