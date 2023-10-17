FROM python:3.10-bookworm

# Create and set workdir
RUN mkdir -p /project
WORKDIR /project

# Define arguments
ARG ZRB_VERSION=latest

# Install zrb
RUN pip install zrb==${ZRB_VERSION}
