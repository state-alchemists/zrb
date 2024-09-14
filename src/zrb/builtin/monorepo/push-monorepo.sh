set -e

CONFLICT="$(git diff --name-only --diff-filter=U)"
if [ -n "${CONFLICT}" ]
then
    log_conflict_error "${CONFLICT}"
    exit 1
fi

git add . -A
if [ -n "$(git status --porcelain)" ]
then
    log_info "Commit changes"
    git commit -m "${MESSAGE}"
fi

log_info "Pushing to main repository"
git push origin "$(git branch --show-current)"
