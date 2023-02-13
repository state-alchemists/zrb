source {{ os.path.expandvars(os.path.expanduser(input.shell_startup)) }}

echo "Install {{ input.python_default_version }}"
pyenv install {{input.python_default_version}}

echo "Set {{ input.python_default_version }} as default"
pyenv global {{input.python_default_version}} --default

echo "Install pipenv"
pip install pipenv

echo "Please reload your terminal to continue (i.e., source {{ input.shell_startup }})"
echo "Happy coding"