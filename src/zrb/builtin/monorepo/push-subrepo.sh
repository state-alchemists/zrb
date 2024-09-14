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

git add . -A
if [ -n "$(git status --porcelain)" ]
then
    log_info "Commit changes"
    git commit -m "${MESSAGE}"
fi

log_info "Pushing to subtree"
git subtree push --prefix "${FOLDER}" "${ORIGIN}" "${BRANCH}"
