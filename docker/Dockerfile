FROM python:3.10-bookworm

# Create and set workdir
RUN mkdir -p /project
WORKDIR /project

# Define arguments
ARG ZRB_VERSION=latest

# Prepare apt
RUN apt update --fix-missing && apt upgrade -y
RUN apt install -y ca-certificates curl gnupg
RUN install -m 0755 -d /etc/apt/keyrings
RUN curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg && \
    chmod a+r /etc/apt/keyrings/docker.gpg && \
    echo \
        "deb [arch="$(dpkg --print-architecture)" signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian \
        "$(. /etc/os-release && echo "$VERSION_CODENAME")" stable" | \
    tee /etc/apt/sources.list.d/docker.list > /dev/null
RUN apt update

# Install packages
RUN apt install -y git ncat curl wget inetutils-tools inetutils-ping \
    build-essential docker.io docker-compose-plugin

# Clean up apt
RUN apt autoremove -yqq --purge && \
    apt clean && \
    rm -rf /var/lib/apt/lists/*

# Install zrb
RUN pip install zrb==${ZRB_VERSION}
