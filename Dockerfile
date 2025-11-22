FROM python:3.13-slim-bookworm

# Build arguments
ARG DIND=false
ARG CI_TOOLS=true

RUN apt-get update && apt-get install -y --no-install-recommends g++

# Install system dependencies (Docker + CI tools if needed)
RUN if [ "$CI_TOOLS" = "true" ]; then \
    apt-get install -y --no-install-recommends git curl wget jq unzip rsync openssh-client; \
fi

# Install Poetry and Python dependencies
RUN pip install poetry && \
    poetry config virtualenvs.create false

WORKDIR /zrb-bin

# Copy the rest of the application
COPY . .
RUN poetry install --without dev

WORKDIR /zrb-home

RUN if [ "$DIND" = "true" ]; then \
    apt-get install -y --no-install-recommends docker.io; \
fi

RUN rm -rf /var/lib/apt/lists/*

CMD ["zrb", "server", "start"]