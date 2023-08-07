set -e
if [ -f './get_helm.sh' ]
then
    echo 'get_helm.sh already downloaded'
else
    curl -fsSL -o get_helm.sh https://raw.githubusercontent.com/helm/helm/master/scripts/get-helm-3
fi

chmod 700 get_helm.sh
./get_helm.sh