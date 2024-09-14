set -e

CONFLICT="$(git diff --name-only --diff-filter=U)"
if [ -n "${CONFLICT}" ]
then
    log_conflict_error "${CONFLICT}"
    exit 1
fi

log_info "Pulling from subtree"
git subtree pull --prefix "${FOLDER}" "${ORIGIN}" "${BRANCH}"

CONFLICT="$(git diff --name-only --diff-filter=U)"
if [ -n "${CONFLICT}" ]
then
    log_conflict_error "${CONFLICT}"
    exit 1
fi