set -e
if [ ! -d "${HOME}/.sdkman" ]
then
    log_info "Download sdkman"
    curl -s "https://get.sdkman.io" | bash
else
    log_info "Sdkman already exists"
fi