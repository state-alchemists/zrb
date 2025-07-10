FROM python:3.13-slim-bookworm

ARG DIND=false

# Create and set workdir
WORKDIR /zrb-bin

# Install poetry
RUN pip install poetry

# Install docker if necessary
RUN if [ "$DIND" = "true" ]; then \
        apt update && \
        apt install -y docker.io && \
        apt clean && \
        rm -rf /var/lib/apt/lists/*; \
    fi

# Configure poetry to not use virtual environments
RUN poetry config virtualenvs.create false

# Copy only the dependency files first
COPY pyproject.toml poetry.lock ./

# Install dependencies
RUN poetry install --without dev --no-root

# Copy the rest of the application code
COPY . .
RUN poetry install --without dev
WORKDIR /zrb-home

CMD ["zrb", "server", "start"]
