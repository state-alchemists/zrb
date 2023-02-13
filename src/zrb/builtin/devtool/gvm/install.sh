source {{ os.path.expandvars(os.path.expanduser(input.shell_startup)) }}

echo "Install {{ input.go_default_version }}"
gvm install {{input.go_default_version}}

echo "Set {{ input.go_default_version }} as default"
gvm use {{input.go_default_version}} --default

echo "Please reload your terminal to continue (i.e., source {{ input.shell_startup }})"
echo "Happy coding"