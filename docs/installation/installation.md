🔖 [Documentation Home](../../README.md) > [Installation](./installation.md)

# Installation & Setup

Getting Zrb set up is straightforward, but it offers a few powerful options depending on your environment and needs. This guide covers everything from a quick `pip` install to advanced containerized and Android setups.

---

## 1. Standard Installation Methods

For most users, installing Zrb with `pip` or using the provided installation script is the recommended approach.

### Using pip (Recommended for Existing Python Setups)

If you already have a Python environment set up, `pip` is the quickest way.

```bash
pip install zrb
# For the latest pre-release version, which often includes the newest features:
# pip install --pre zrb
```

### Using the Installation Script (Recommended for New Python/System Setups)

The `install.sh` script is a powerful helper that automates the installation of Zrb and its common prerequisites, including Python environment management (like `pyenv` or a local virtual environment). This is especially useful if your system doesn't have Python set up optimally or you want a self-contained Zrb environment.

**How it Works:**
The script is interactive and will ask for your consent to install various components:
-   **Python Environment:** It can install `pyenv` to manage Python versions (and then install Python 3.13.0 globally) or create a local virtual environment in `~/.local-venv`.
-   **System Prerequisites:** It attempts to install necessary build tools and libraries (`build-essential`, `libssl-dev`, etc.) using your OS's package manager (`brew` on macOS, `apt`, `yum`, `dnf`, `pacman`, `apk` on Linux).
-   **Poetry:** It can install the Poetry package manager.
-   **Zrb:** Finally, it installs Zrb itself using `pip`.

```bash
bash -c "$(curl -fsSL https://raw.githubusercontent.com/state-alchemists/zrb/main/install.sh)"
```

**What the Script Does (Detailed Breakdown):**
-   **`command_exists`**: Utility to check if a command is available.
-   **`log_info`**: Formatted info messages.
-   **`confirm`**: Prompts for `y/N` confirmation before making changes.
-   **`try_sudo`**: Executes commands with `sudo` if available.
-   **`register_pyenv`**: Adds `pyenv` initialization lines to your shell's rc file (`.zshrc`, `.bashrc`).
-   **`register_local_venv`**: Adds lines to activate a `~/.local-venv` and generate autocompletion scripts for Zrb.
-   **`create_and_register_local_venv`**: Creates `~/.local-venv`, activates it, and registers it to your shell.
-   **`install_pyenv`**: Installs `pyenv` via `curl https://pyenv.run | bash` and registers it.
-   **`install_python_on_pyenv`**: Installs Python 3.13.0 and sets it as global using `pyenv`.
-   **`install_poetry`**: Installs Poetry using `pip`.
-   **`install_zrb`**: Installs Zrb using `pip install --pre zrb`.

The script handles Termux-specific installations (changing repos, `termux-setup-storage`, `pkg install` for various tools) if it detects an Android environment.

---

## 2. Advanced Installation Methods

For specialized use cases like CI/CD pipelines or running automation on the go, Zrb offers containerized and mobile options.

### Running Zrb in a Docker Container

Zrb provides container images for sandboxed, reproducible, and portable execution. This is ideal for consistent environments and CI/CD integration (see [CI/CD Integration](../advanced-topics/ci-cd.md)).

-   **Standard Image**: For general-purpose automation. It comes with Zrb and its basic Python dependencies.
    ```bash
    docker run -v ${HOME}:/zrb-home -it --rm stalchmst/zrb:2.0.0 zrb
    ```
    *Explanation*:
    -   `-v ${HOME}:/zrb-home`: Mounts your host machine's home directory into the container at `/zrb-home`. This allows Zrb inside the container to access your `zrb_init.py` files, project directories, and any LLM history/journal files.
    -   `-it`: Interactive and pseudo-TTY.
    -   `--rm`: Automatically remove the container when it exits.
    -   `stalchmst/zrb:2.0.0`: The official Zrb Docker image (always pin to a specific version!).
    -   `zrb`: The command to execute inside the container.

-   **DIND (Docker-in-Docker) Image**: For tasks that need to execute Docker commands *from within* the Zrb pipeline (e.g., building new Docker images, running `docker compose`).
    ```bash
    docker run 
        -v ${HOME}:/zrb-home 
        -v /var/run/docker.sock:/var/run/docker.sock 
        -it --rm stalchmst/zrb:2.0.0-dind docker ps
    ```
    *Explanation (additional to Standard Image)*:
    -   `-v /var/run/docker.sock:/var/run/docker.sock`: This crucial mount allows the Docker client inside the Zrb container to communicate with the Docker daemon running on your host machine. This enables "Docker-in-Docker" functionality.
    -   `stalchmst/zrb:2.0.0-dind`: The DIND-enabled Zrb Docker image.

### Running Zrb on Android (via Termux and Proot)

You can run Zrb on your Android device using Termux (a terminal emulator and Linux environment) and Proot (a chroot-like environment). This turns your phone into a portable automation powerhouse.

**Prerequisites for Android:**
*   An Android device with an internet connection.
*   **Termux:** Download and install the [F-Droid](https://f-droid.org/en/packages/com.termux/) client, then install Termux from there. The Google Play Store version is outdated.
*   **Optional Termux Packages:** `Termux-Styling`, `Termux-API`, `Termux-Storage` (from F-Droid).

**Step-by-Step Android Setup:**

1.  **Update Termux Packages:**
    Open Termux and run:
    ```bash
    pkg update && pkg upgrade -y
    ```

2.  **Install Proot and a Linux Distribution (e.g., Ubuntu):**
    Proot allows you to run a full Linux distribution within Termux.
    ```bash
    pkg install proot proot-distro -y
    proot-distro install ubuntu
    ```
    *(Note: Proot Linux distributions have better software compatibility than bare Termux, but some limitations exist, e.g., Docker is challenging due to Android's kernel.)*

3.  **Login to Ubuntu Environment:**
    ```bash
    proot-distro login ubuntu
    ```
    Your terminal prompt will change to indicate you are now inside Ubuntu.

4.  **Install Python and Pip (inside Ubuntu):**
    ```bash
    apt update
    apt install python3 python3-pip python3-venv -y
    ```
    Verify: `python3 --version` and `pip3 --version`.

5.  **Install Zrb (inside Ubuntu):**
    ```bash
    pip3 install zrb
    ```
    Verify: `zrb --version`.

6.  **Using Zrb on Android:**
    -   You can now use `zrb` commands as usual.
    -   To access your phone's internal storage, you might need to navigate to `/data/data/com.termux/files/home/storage/shared` within the Ubuntu environment.
    -   To exit Ubuntu: `exit`. To exit Termux: `exit` again.

---

## 3. General Configuration

Zrb's behavior can be customized further using environment variables. This includes everything from logging levels to default editors and web UI settings. For a complete, exhaustive list of all configurable environment variables, please refer to the dedicated configuration guides:

-   [Environment Variables & Overrides](../configuration/env-vars.md)
-   [LLM & Rate Limiter Configuration](../configuration/llm-config.md)

---
