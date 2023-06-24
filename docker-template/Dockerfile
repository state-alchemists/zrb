FROM debian:bookworm-slim

# Create and set workdir
RUN mkdir -p /project
WORKDIR /project

# Update and set third party repositories
RUN apt-get update --fix-missing && apt-get upgrade -y
RUN apt-get install -y ca-certificates curl gnupg
RUN install -m 0755 -d /etc/apt/keyrings
RUN curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg && \
    chmod a+r /etc/apt/keyrings/docker.gpg && \
    echo \
        "deb [arch="$(dpkg --print-architecture)" signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian \
        "$(. /etc/os-release && echo "$VERSION_CODENAME")" stable" | \
    tee /etc/apt/sources.list.d/docker.list > /dev/null
RUN apt-get update

# Install packages
RUN apt-get install -y git ncat curl wget inetutils-tools inetutils-ping \
        docker.io docker-compose-plugin zsh python-is-python3 pip \
        build-essential libssl-dev zlib1g-dev \
        libbz2-dev libreadline-dev libsqlite3-dev curl \
        libncursesw5-dev xz-utils tk-dev libxml2-dev libxmlsec1-dev libffi-dev liblzma-dev && \
    apt-get autoremove -yqq --purge && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Install pyenv
RUN curl https://pyenv.run | bash

# Configure pyenv for bash shell
RUN echo 'export PYENV_ROOT="$HOME/.pyenv"' >> ~/.bashrc
RUN echo 'command -v pyenv >/dev/null || export PATH="$PYENV_ROOT/bin:$PATH"' >> ~/.bashrc
RUN echo 'eval "$(pyenv init -)"' >> ~/.bashrc

# Install Python 3.10 on pyenv
RUN bash -c 'source ~/.bashrc && pyenv install 3.11 && pyenv global 3.11'

# Configure zsh shell
RUN sh -c "$(curl -fsSL https://raw.github.com/ohmyzsh/ohmyzsh/master/tools/install.sh)"

RUN echo 'export PYENV_ROOT="$HOME/.pyenv"' >> ~/.zshrc
RUN echo 'command -v pyenv >/dev/null || export PATH="$PYENV_ROOT/bin:$PATH"' >> ~/.zshrc
RUN echo 'eval "$(pyenv init -)"' >> ~/.zshrc

# Install Zrb on top of pyenv
RUN bash -c 'source ~/.bashrc && pip install zrb==zrb_version'

# Prepare environments
ENV DEBIAN_FRONTEND=noninteractive

# Set command
CMD ["bash", "-c", "echo 'To start working, invoke: docker exec -it <this-container-name> zsh' && sleep infinity"]