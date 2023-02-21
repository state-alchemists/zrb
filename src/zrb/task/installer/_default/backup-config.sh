set -e
{% if input.config_file %}
if [ -f '{{input.config_file}}' ]
then
    echo 'Backup {{input.config_file}} to {{input.config_file}}.bak'
    cp '{{input.config_file}}' '{{input.config_file}}.bak'
else
    echo 'Nothing to backup'
fi
{% else %}
echo 'Nothing to backup'
{% endif %}