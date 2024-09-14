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
    git commit -m "Before pulling from monorepo at ${TIME}"
fi

log_info "Pulling from main repository"
git pull origin "$(git branch --show-current)"
