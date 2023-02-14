source {{ os.path.expandvars(os.path.expanduser(input.shell_startup)) }}

if [ ! -d "${HOME}/.nvm/versions/{{ input.node_default_version }}" ]
then
    echo "Install {{ input.node_default_version }}"
    nvm install {{ input.node_default_version }}
else
    echo "{{ input.node_default_version }} already installed"
fi

echo "Set {{ input.node_default_version }} as default"
nvm use {{input.node_default_version}}
nvm alias default {{input.node_default_version}}

echo "Please reload your terminal to continue (i.e., source {{ input.shell_startup }})"
echo "Happy coding"