source {{ os.path.expandvars(os.path.expanduser(input.config_file)) }}

set -e
{% if input.install_java %}
echo "Install Java"
sdk install java
{% endif %}

{% if input.install_scala %}
echo "Install Scala"
sdk install scala
{% endif %}

echo "Please reload your terminal to continue (i.e., source {{ input.config_file }})"
echo "Happy coding"