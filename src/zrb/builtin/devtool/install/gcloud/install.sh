if command_exists apt
then
    log_info "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] https://packages.cloud.google.com/apt cloud-sdk main" |try_sudo tee -a /etc/apt/sources.list.d/google-cloud-sdk.list
    try_sudo apt install -y apt-transport-https ca-certificates gnupg
    curl https://packages.cloud.google.com/apt/doc/apt-key.gpg |try_sudo apt-key --keyring /usr/share/keyrings/cloud.google.gpg add -
    try_sudo apt update &&try_sudo apt install -y google-cloud-sdk
else
    log_info "apt not found"
    exit 1
fi

