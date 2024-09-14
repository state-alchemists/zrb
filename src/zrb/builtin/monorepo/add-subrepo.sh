set -e

if [ -d "${FOLDER}" ]
then
    exit 0
fi

CONFLICT="$(git diff --name-only --diff-filter=U)"
if [ -n "${CONFLICT}" ]
then
    log_conflict_error "${CONFLICT}"
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
