source {{ os.path.expandvars(os.path.expanduser(input.shell_startup)) }}

echo "Please reload your terminal to continue (i.e., source {{ input.shell_startup }})"
echo "Happy coding"