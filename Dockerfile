FROM python:3.13-slim-bookworm

ARG DIND=false

# Create and set workdir
WORKDIR /zrb-home

# Prepare apt and install poetry in a single layer
RUN apt update --fix-missing && \
    apt upgrade -y && \
    apt install -y --no-install-recommends curl && \
    apt autoremove -yqq --purge && \
    apt clean && \
    rm -rf /var/lib/apt/lists/* && \
    pip install poetry

# Configure poetry to not use virtual environments
RUN poetry config virtualenvs.create false

# Copy only the dependency files first
COPY pyproject.toml poetry.lock ./

# Install dependencies
RUN poetry install --without dev --no-root

# Copy the rest of the application code
COPY . .
RUN poetry install --without dev

RUN if [ "$DIND" = "true" ]; then \
        apt update && \
        apt install -y docker.io && \
        apt clean && \
        rm -rf /var/lib/apt/lists/*; \
    fi

CMD ["zrb", "server", "start"]
