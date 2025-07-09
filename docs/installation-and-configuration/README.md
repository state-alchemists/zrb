🔖 [Home](../../README.md) > [Documentation](../README.md)

---

# Installation and Configuration

Getting Zrb set up is straightforward. This guide will walk you through installing Zrb on your system, configuring it for AI-powered features, and exploring advanced installation options.

---

## 1. Standard Installation

For most users, installing Zrb with `pip` or the installation script is the recommended approach.

### Using pip (Recommended)

The easiest way to install Zrb is with `pip`, the Python package installer.

```bash
pip install zrb
# For the latest pre-release version:
# pip install --pre zrb
```

### Using the Installation Script

Alternatively, you can use a convenient script that handles all prerequisites for you.

```bash
bash -c "$(curl -fsSL https://raw.githubusercontent.com/state-alchemists/zrb/main/install.sh)"
```

---

## 2. LLM Configuration (for AI Features)

To unlock Zrb's powerful AI capabilities, you need to connect it to a Large Language Model (LLM).

### The Quickest Way: OpenAI

The simplest method is to set your OpenAI API key as an environment variable.

```bash
export OPENAI_API_KEY="your-openai-api-key-here"
```

Once this is set, Zrb can immediately use OpenAI for tasks like `zrb llm chat` and `zrb llm ask`.

> **💡 No OpenAI key? No problem!**
> Zrb supports a wide range of LLM providers, including open-source models running locally with Ollama. For detailed instructions on configuring other providers, see the [**LLM Integration Guide**](./configuration/llm-integration.md).

---

## 3. Advanced Installation Methods

For specialized use cases like CI/CD pipelines or running automation on the go, Zrb offers containerized and mobile options.

### Running Zrb in a Docker Container

Zrb provides container images for sandboxed and portable execution. This is ideal for consistent environments and CI/CD integration.

-   **Standard Image**: For general-purpose automation.
    ```bash
    docker run -v ${HOME}:/zrb-home -it --rm stalchmst/zrb:1.8.1 zrb
    ```
-   **DIND (Docker-in-Docker) Image**: For tasks that need to execute Docker commands.
    ```bash
    docker run \
        -v ${HOME}:/zrb-home \
        -v /var/run/docker.sock:/var/run/docker.sock \
        -it --rm stalchmst/zrb:1.8.1-dind docker ps
    ```

### Running Zrb on Android

You can run Zrb on your Android device using Termux, turning your phone into a portable automation powerhouse.

For step-by-step instructions, see the [**Run Zrb on Android Guide**](./run-zrb-on-android.md).

---

## 4. General Configuration

Zrb's behavior can be customized further using environment variables. You can control logging levels, default editors, web UI settings, and much more.

For a complete list of available environment variables and how to set them, please refer to the [**Configuration Guide**](./configuration/README.md).

---

🔖 [Home](../../README.md) > [Documentation](../README.md)

➡️ [Next: Core Concepts](../core-concepts/README.md)