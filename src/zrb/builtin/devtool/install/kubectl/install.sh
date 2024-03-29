set -e
if [ -f './kubectl' ]
then
    log_info 'kubectl already downloaded'
else
    curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
fi

sudo install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl
