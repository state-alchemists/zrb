log_info() {
    echo -e "🤖 \e[0;33m${1}\e[0;0m"
}

log_error() {
    echo -e "\e[1;31m${1}\e[0;0m" >&2
}

log_conflict_error() {
    log_error "Action blocked by unresolved conflicts."
    log_error "You need to resolve the conflict(s) and commit the changes."
    log_error "Unresolved conflict(s) detected:"
    log_error "$1"
}

