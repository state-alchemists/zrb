set -e
OS_TYPE=$(uname)

command_exists() {
    command -v "$1" &> /dev/null
}

try_sudo() {
    if command_exists sudo
    then
        sudo $@
    else
        $@
    fi
}

log_info() {
    echo -e "🤖 \e[0;33m${1}\e[0;0m"
}
