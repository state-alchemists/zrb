echo "Git add"
git add . -A

echo "Remove dist"
rm -Rf dist

echo "Build"
flit build
