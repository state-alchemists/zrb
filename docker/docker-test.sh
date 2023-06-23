# /bin/bash
set -e
docker build . -t stalchmst/zrb
docker run -d --name zrb --add-host=host.docker.internal:host-gateway -v /var/run/docker.sock:/var/run/docker.sock  --rm stalchmst/zrb:latest
docker exec -it zrb bash
