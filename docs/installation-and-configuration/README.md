🔖 [Home](../../README.md) > [Documentation](../README.md)

# Installation and Configuration

## Installation

The easiest way to install Zrb is using pip:

```bash
pip install zrb
# pip install --pre zrb
```

Alternatively, you can use Zrb installation script which handles prerequisites:

```bash
bash -c "$(curl -fsSL https://raw.githubusercontent.com/state-alchemists/zrb/main/install.sh)"
```

## Run Zrb as a Container

Zrb can be run in a containerized environment, perfect for CI/CD integration. Zrb offering two distinct images to suit different needs:

- **Standard Version**: Ideal for general use cases where Docker CLI access is not required.
- **Dind (Docker in Docker) Version**: Includes built-in Docker commands, perfect for scenarios where you need to access the host's Docker CLI.

### Standard Version

The standard version of the Zrb container is suitable for most automation tasks. To run this version, execute the following command:

```bash
# Replace <host-path> and <container-path> with your desired paths
docker run -v ${HOME}:/zrb-home -it --rm stalchmst/zrb:1.8.1 zrb
```

### Docker in Docker (Dind) Version

The Dind version is tailored for advanced use cases where Docker commands need to be executed within the container. This version allows the container to interact with the host's Docker daemon. To run the Dind version, use the command below:

```bash
# Replace <host-path> and <container-path> with your desired paths
docker run \
    -v ${HOME}:/zrb-home \
    -v /var/run/docker.sock:/var/run/docker.sock \
    -it --rm stalchmst/zrb:1.8.1-dind docker ps
```

> **Note:** The Dind (Docker in Docker) version of the container is larger in size compared to the standard version due to the inclusion of Docker CLI tools. Consider this when choosing the appropriate version for your needs.

## Run Zrb on Android

[Run Zrb on Android](./run-zrb-on-android.md)

