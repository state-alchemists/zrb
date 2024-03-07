source {{ os.path.expandvars(os.path.expanduser(input.config_file)) }}

set -e
if [ ! -d "${HOME}/.nvm/versions/{{ input.node_default_version }}" ]
then
    log_info "Install {{ input.node_default_version }}"
    nvm install {{ input.node_default_version }}
else
    log_info "{{ input.node_default_version }} already installed"
fi

log_info "Set {{ input.node_default_version }} as default"
nvm use {{input.node_default_version}}
nvm alias default {{input.node_default_version}}

log_info "Please reload your terminal to continue (i.e., source {{ input.config_file }})"
