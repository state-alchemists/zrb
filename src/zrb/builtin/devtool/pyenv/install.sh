source {{ os.path.expandvars(os.path.expanduser(input.shell_startup)) }}

if [ ! -d "${HOME}/.pyenv/versions/{{ input.python_default_version }}" ]
then
    echo "Install Python {{ input.python_default_version }}"
    pyenv install {{input.python_default_version}}
else
    echo "Python {{ input.python_default_version }} already installed"
fi

echo "Set Python {{ input.python_default_version }} as default"
pyenv global {{input.python_default_version}}

echo "Install pipenv"
pip install pipenv

echo "Please reload your terminal to continue (i.e., source {{ input.shell_startup }})"
echo "Happy coding"