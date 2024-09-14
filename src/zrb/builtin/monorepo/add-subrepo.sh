set -e

log_info() {
    echo -e "🤖 \e[0;33m${1}\e[0;0m"
}

log_error() {
    echo -e "\e[1;31m${1}\e[0;0m" >&2
}

if [ -d "${FOLDER}" ]
then
    exit 0
fi

CONFLICT="$(git diff --name-only --diff-filter=U)"
if [ -n "${CONFLICT}" ]
then
    log_error "Unresolved conflicts detected: ${CONFLICT}"
    exit 1
fi

log_info "Adding subtree: ${FOLDER}"
git subtree add --prefix "${FOLDER}" "${ORIGIN}" "${BRANCH}"
git add . -A
if [ -n "$(git status --porcelain)" ]
then
    log_info "Commit changes"
    git commit -m "Adding subtree: ${FOLDER} at ${TIME}"
fi
