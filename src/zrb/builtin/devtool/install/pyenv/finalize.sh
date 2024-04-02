source {{ os.path.expandvars(os.path.expanduser(input.config_file)) }}

set -e
if [ ! -d "${HOME}/.pyenv/versions/{{ input.python_default_version }}" ]
then
    log_info "Install Python {{ input.python_default_version }}"
    pyenv install {{input.python_default_version}}
else
    log_info "Python {{ input.python_default_version }} already installed"
fi

log_info "Set Python {{ input.python_default_version }} as default"
pyenv global {{input.python_default_version}}

log_info "Install pipenv"
pip install pipenv

log_info "Please reload your terminal to continue (i.e., source {{ input.config_file }})"