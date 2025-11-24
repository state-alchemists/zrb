FROM python:3.13-slim-bookworm AS normal

# set workdir
WORKDIR /zrb-bin

# install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends g++ && rm -rf /var/lib/apt/lists/*

# install ci-tools
ARG CI_TOOLS=true
RUN if [ "$CI_TOOLS" = "true" ]; then \
    apt-get update && apt-get install -y --no-install-recommends git curl wget jq unzip rsync openssh-client && rm -rf /var/lib/apt/lists/*; \
    fi

# install poetry
RUN pip install poetry
RUN poetry config virtualenvs.create false

# copy app source
COPY . .
RUN poetry install --without dev

WORKDIR /zrb-home

CMD ["zrb", "server", "start"]


#
# ===== DIND image =====
#
FROM normal AS dind

RUN apt-get update && apt-get install -y --no-install-recommends docker.io && rm -rf /var/lib/apt/lists/*