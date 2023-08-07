source {{ os.path.expandvars(os.path.expanduser(input.config_file)) }}

set -e
if [ ! -d "${HOME}/.gvm/gos/{{ input.go_default_version }}" ]
then
    echo "Install {{ input.go_default_version }}"
    gvm install {{input.go_default_version}}
else
    echo "{{ input.go_default_version }} already installed"
fi

echo "Set {{ input.go_default_version }} as default"
gvm use "{{input.go_default_version}}" --default

echo "Please reload your terminal to continue (i.e., source {{ input.config_file }})"
echo "Happy coding"