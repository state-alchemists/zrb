set -e
helm version
if [ "$?" != 0 ]
then
  >&2 echo "helm not found"
  exit 1
fi