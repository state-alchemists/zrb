set -e
cd {{input.project_dir}}
if [ ! -d .git ]
then
    log_info "Initialize git repository"
    git init
fi