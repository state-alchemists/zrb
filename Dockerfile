FROM python:3.10-bookworm

# Create and set workdir
RUN mkdir -p /project
WORKDIR /project

# Prepare apt
RUN apt update --fix-missing && apt upgrade -y
RUN apt update

# Clean up apt
RUN apt autoremove -yqq --purge && \
    apt clean && \
    rm -rf /var/lib/apt/lists/*

# Install zrb
RUN pip install poetry
RUN poetry install