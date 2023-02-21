set -e
{% if input.config_file %}
if [ -f '{{input.config_file}}' ]
then
    echo 'Remove {{input.config_file}}'
    rm '{{input.config_file}}'
else
    echo 'Nothing to remove'
fi
{% else %}
echo 'Nothing to remove'
{% endif %}