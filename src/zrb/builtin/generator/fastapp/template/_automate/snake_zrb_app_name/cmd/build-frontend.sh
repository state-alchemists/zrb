echo "Installing node packages, might take a while"
npm install --save-dev
echo "Building frontend"
npm run build{{ ':watch' if env.WATCH == '1' else '' }}