source {{ os.path.expandvars(os.path.expanduser(input.config_file)) }}

set -e
if [ ! -d "${HOME}/.gvm/gos/{{ input.go_default_version }}" ]
then
    log_info "Install {{ input.go_default_version }}"
    gvm install {{input.go_default_version}}
else
    log_info "{{ input.go_default_version }} already installed"
fi

log_info "Set {{ input.go_default_version }} as default"
gvm use "{{input.go_default_version}}" --default

log_info "Please reload your terminal to continue (i.e., source {{ input.config_file }})"
log_info "Happy coding"