source {{ os.path.expandvars(os.path.expanduser(input.shell_startup)) }}

{% if input.install_java %}
echo "Install Java"
sdk install java
{% endif %}

{% if input.install_scala %}
echo "Install Scala"
sdk install scala
{% endif %}

echo "Please reload your terminal to continue (i.e., source {{ input.shell_startup }})"
echo "Happy coding"