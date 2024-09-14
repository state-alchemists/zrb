set -e

log_info() {
    echo -e "🤖 \e[0;33m${1}\e[0;0m"
}

log_error() {
    echo -e "\e[1;31m${1}\e[0;0m" >&2
}

CONFLICT="$(git diff --name-only --diff-filter=U)"
if [ -n "${CONFLICT}" ]
then
    log_error "Unresolved conflicts detected: ${CONFLICT}"
    exit 1
fi

log_info "Pulling from subtree"
git subtree pull --prefix "${FOLDER}" "${ORIGIN}" "${BRANCH}"

CONFLICT="$(git diff --name-only --diff-filter=U)"
if [ -n "${CONFLICT}" ]
then
    log_error "Unresolved conflicts detected: ${CONFLICT}"
    exit 1
fi