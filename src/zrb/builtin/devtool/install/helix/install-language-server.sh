set +e

pip --version
if [ "$?" = 0 ]
then
    echo "Install python language server"
    pip install -U 'python-lsp-server[all]'
else
    echo "Cannot install python language server, is pip installed?"
fi

npm --version
if [ "$?" = 0 ]
then
    echo "Install docker language server"
    npm install -g dockerfile-language-server-nodejs
else
    echo "Cannot install docker language server, is npm installed?"
fi

go version
if [ "$?" = 0 ]
then
    echo "Install go language server"
    go install golang.org/x/tools/gopls@latest          # LSP
    go install github.com/go-delve/delve/cmd/dlv@latest # Debugger
    go install golang.org/x/tools/cmd/goimports@latest  # Formatter
else
    echo "Cannot install go language server, is go installed?"
fi

if command_exists hx
then
    hx --grammar fetch
    hx --grammar build
elif command_exists helix
then
    helix --grammar fetch
    helix --grammar build
fi

set -e
echo "Visit https://github.com/helix-editor/helix/wiki/How-to-install-the-default-language-servers for more information."
