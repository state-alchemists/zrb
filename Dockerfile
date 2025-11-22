FROM python:3.13-slim-bookworm

# Build arguments
ARG DIND=false
ARG CI_TOOLS=true

# Install system dependencies (Docker + CI tools if needed)
RUN if [ "$CI_TOOLS" = "true" ] || [ "$DIND" = "true" ]; then \
    apt-get update && \
    apt-get install -y --no-install-recommends \
    $(if [ "$CI_TOOLS" = "true" ]; then echo "git curl wget jq unzip rsync openssh-client"; fi) \
    $(if [ "$DIND" = "true" ]; then echo "docker.io"; fi) \
    && \
    rm -rf /var/lib/apt/lists/*; \
fi

# Install Poetry and Python dependencies
RUN pip install poetry && \
    poetry config virtualenvs.create false

WORKDIR /zrb-bin
COPY pyproject.toml poetry.lock ./
RUN poetry install --without dev --no-root

# Copy the rest of the application
COPY . .
RUN poetry install --without dev

WORKDIR /zrb-home
CMD ["zrb", "server", "start"]