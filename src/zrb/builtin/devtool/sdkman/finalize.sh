source {{ os.path.expandvars(os.path.expanduser(input.config_file)) }}

set -e
{% if input.install_java %}
log_info "Install Java"
sdk install java
{% endif %}

{% if input.install_scala %}
log_info "Install Scala"
sdk install scala
{% endif %}

log_info "Please reload your terminal to continue (i.e., source {{ input.config_file }})"
log_info "Happy coding"