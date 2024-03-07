set -e
if [ ! -d "${HOME}/.nvm" ]
then
    log_info "Download nvm"
    curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.3/install.sh | bash
else
    log_info "Nvm already exists"
fi