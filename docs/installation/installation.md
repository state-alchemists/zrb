🔖 [Documentation Home](../../README.md) > [Installation](./installation.md)

# Installation & Setup

Getting Zrb set up is straightforward, but it offers a few powerful options depending on your environment and needs. This guide covers everything from a quick `pip` install to advanced containerized and Android setups.

---

## 🚀 Quick Start

**Already have Python installed? Get started in seconds:**

```bash
pip install zrb
zrb --version
```

**New to Python or setting up a fresh system?** Use our one-liner installer:

```bash
# Linux/macOS
bash -c "$(curl -fsSL https://raw.githubusercontent.com/state-alchemists/zrb/main/install.sh)"

# Windows (PowerShell)
powershell -ExecutionPolicy Bypass -Command "iex ((New-Object System.Net.WebClient).DownloadString('https://raw.githubusercontent.com/state-alchemists/zrb/main/install.ps1'))"
```

---

## Which Method Should I Choose?

| Situation | Recommended Method | Why |
|-----------|-------------------|-----|
| ✅ Python already installed | `pip install zrb` | Fastest, simplest |
| 🆕 Fresh system / No Python | Installation script | Handles Python setup automatically |
| 🪟 Windows | PowerShell script | Native Windows support |
| 🐳 CI/CD pipelines | Docker image | Reproducible, isolated environment |
| 📱 Android / Mobile | Termux + Proot | Run automation on your phone |
| 🍎 Apple Silicon (M1/M2/M3) | `pip install` or Docker | Fully supported |

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

### Using the Installation Script - Bash (Recommended for New Python/System Setups)

The `install.sh` script is a powerful helper that automates the installation of Zrb and its common prerequisites, including Python environment management (like `pyenv` or a local virtual environment). This is especially useful if your system doesn't have Python set up optimally or you want a self-contained Zrb environment.

**What it sets up:**
-   **Python Environment:** Installs `pyenv` to manage Python versions (and sets Python 3.13.0 globally) or creates a local virtual environment in `~/.local-venv`.
-   **System Prerequisites:** Installs build tools and libraries (`build-essential`, `libssl-dev`, etc.) using your OS's package manager (`brew` on macOS, `apt`, `yum`, `dnf`, `pacman`, `apk` on Linux).
-   **Poetry:** Optionally installs the Poetry package manager.
-   **Zrb:** Installs Zrb itself using `pip`.

> 💡 **Tip:** The script is interactive and will ask for your consent before each change.

**Run from GitHub (recommended):**

```bash
bash -c "$(curl -fsSL https://raw.githubusercontent.com/state-alchemists/zrb/main/install.sh)"
```

**Run locally:**

```bash
bash install.sh
```

<details>
<summary>📜 Script Functions Reference</summary>

The script includes these helper functions:

| Function | Purpose |
|----------|---------|
| `command_exists` | Check if a command is available |
| `log_info` | Format and display info messages |
| `confirm` | Prompt for `y/N` confirmation before changes |
| `try_sudo` | Execute commands with `sudo` if available |
| `register_pyenv` | Add `pyenv` init lines to shell rc file |
| `register_local_venv` | Register `~/.local-venv` activation in shell |
| `create_and_register_local_venv` | Create and activate virtual environment |
| `install_pyenv` | Install pyenv via `curl https://pyenv.run \| bash` |
| `install_python_on_pyenv` | Install Python 3.13.0 and set as global |
| `install_poetry` | Install Poetry package manager |
| `install_zrb` | Install Zrb via `pip install --pre zrb` |

</details>

> ⚠️ **Note:** The script handles Termux-specific installations (Android) automatically if detected.

### Using the Installation Script - PowerShell (Windows)

For Windows users, Zrb provides a PowerShell installation script (`install.ps1`) that simplifies setup.

**Prerequisites:**
-   Python 3.11 or later (install before running the script)

**Install Python on Windows (if needed):**

```powershell
# Option 1: Using winget (recommended)
winget install Python.Python.3.13

# Option 2: Download from python.org
# Visit: https://www.python.org/downloads/

# Option 3: Microsoft Store
# Search for "Python 3.13" in Microsoft Store
```

**Run from GitHub (recommended):**

```powershell
powershell -ExecutionPolicy Bypass -Command "iex ((New-Object System.Net.WebClient).DownloadString('https://raw.githubusercontent.com/state-alchemists/zrb/main/install.ps1'))"
```

**Run locally:**

```powershell
powershell -ExecutionPolicy Bypass -File install.ps1
```

<details>
<summary>📝 Manual Windows Installation</summary>

If you prefer manual installation or already have Python set up:

```powershell
# Basic installation
pip install --pre zrb

# Create a virtual environment (optional)
python -m venv ~/.local-venv
~/.local-venv/Scripts/Activate.ps1
pip install --pre zrb
```

**Windows-Specific Notes:**
-   The PowerShell profile location is `$PROFILE` (typically `Documents\PowerShell\Microsoft.PowerShell_profile.ps1`)
-   For virtual environment activation, use `.ps1` scripts (e.g., `Scripts\Activate.ps1`)
-   If using PowerShell 7+, the profile path may differ from Windows PowerShell 5.1

</details>

---

## 2. Advanced Installation Methods

For specialized use cases like CI/CD pipelines or running automation on the go, Zrb offers containerized and mobile options.

### Running Zrb in a Docker Container

Zrb provides container images for sandboxed, reproducible, and portable execution. This is ideal for consistent environments and CI/CD integration (see [CI/CD Integration](../advanced-topics/ci-cd.md)).

**Standard Image** (general-purpose automation):

```bash
docker run -v ${HOME}:/zrb-home -it --rm stalchmst/zrb:2.0.0 zrb
```

**DIND (Docker-in-Docker) Image** (for tasks that need Docker commands):

```bash
docker run \
    -v ${HOME}:/zrb-home \
    -v /var/run/docker.sock:/var/run/docker.sock \
    -it --rm stalchmst/zrb:2.0.0-dind docker ps
```

<details>
<summary>🔧 Docker Options Explained</summary>

| Option | Purpose |
|--------|---------|
| `-v ${HOME}:/zrb-home` | Mount home directory for access to `zrb_init.py` files |
| `-it` | Interactive mode with TTY |
| `--rm` | Remove container on exit |
| `-v /var/run/docker.sock:...` | Enable Docker-in-Docker functionality |

> 💡 **Tip:** Always pin to a specific version (e.g., `2.0.0`) for reproducibility.

</details>

> ⚠️ **Apple Silicon:** Use `--platform linux/amd64` if you encounter architecture issues:
> ```bash
> docker run --platform linux/amd64 -v ${HOME}:/zrb-home -it --rm stalchmst/zrb:2.0.0 zrb
> ```

### Running Zrb on Android (via Termux and Proot)

You can run Zrb on your Android device using Termux (a terminal emulator and Linux environment) and Proot (a chroot-like environment). This turns your phone into a portable automation powerhouse.

**Prerequisites:**
-   An Android device with an internet connection
-   **Termux:** Install from [F-Droid](https://f-droid.org/en/packages/com.termux/) (NOT Google Play - outdated version)

**Quick Setup:**

```bash
# 1. Update Termux
pkg update && pkg upgrade -y

# 2. Install Proot and Ubuntu
pkg install proot proot-distro -y
proot-distro install ubuntu

# 3. Login to Ubuntu
proot-distro login ubuntu

# 4. Install Python (inside Ubuntu)
apt update && apt install python3 python3-pip python3-venv -y

# 5. Install Zrb
pip3 install zrb

# 6. Verify
zrb --version
```

<details>
<summary>📖 Detailed Android Setup</summary>

**Optional Termux Packages:** `Termux-Styling`, `Termux-API`, `Termux-Storage` (from F-Droid)

**Using Zrb on Android:**
-   Access phone storage at `/data/data/com.termux/files/home/storage/shared`
-   Exit Ubuntu: `exit`
-   Exit Termux: `exit` again

> ⚠️ **Note:** Docker is challenging on Android due to kernel limitations. Proot Linux distributions have better software compatibility than bare Termux.

</details>

---

## 3. Verify Installation

After installing Zrb, verify everything is working:

```bash
# Check version
zrb --version

# View help
zrb --help

# Quick test - create a simple task
echo 'from zrb import cli, CmdTask
cli.add_task(CmdTask(name="hello", cmd="echo Hello from Zrb!"))' > zrb_init.py

# Run the task
zrb hello
```

**Expected output:**
```
Hello from Zrb!
```

---

## 4. Shell Autocomplete

Zrb supports tab completion for Bash, Zsh, and PowerShell.

### Bash

Add to `~/.bashrc`:

```bash
eval "$(zrb shell autocomplete bash)"
```

Then reload: `source ~/.bashrc`

### Zsh

Add to `~/.zshrc`:

```zsh
eval "$(zrb shell autocomplete zsh)"
```

Then reload: `source ~/.zshrc`

### PowerShell

Add to your PowerShell profile (`$PROFILE`):

```powershell
(zrb shell autocomplete powershell) -join "`n" | Invoke-Expression
```

To edit your profile:

```powershell
notepad $PROFILE
```

> 💡 **Tip:** If `$PROFILE` does not exist yet, create it first: `New-Item -Path $PROFILE -ItemType File -Force`

---

## 5. Upgrade Zrb

**Upgrade with pip:**

```bash
pip install --upgrade zrb

# For latest pre-release:
pip install --upgrade --pre zrb
```

**Upgrade with Docker:**

Pull the latest image:
```bash
docker pull stalchmst/zrb:2.0.0
# Or for latest:
docker pull stalchmst/zrb:latest
```

---

## 6. Uninstall Zrb

**Uninstall with pip:**

```bash
pip uninstall zrb
```

**Clean up virtual environment (if created by install script):**

```bash
rm -rf ~/.local-venv
```

**Remove pyenv (if installed by script):**

```bash
# Remove pyenv directory
rm -rf ~/.pyenv

# Remove pyenv lines from your shell rc file (~/.bashrc, ~/.zshrc, etc.)
# Look for and delete lines containing 'pyenv'
```

---

## 7. Troubleshooting

### Common Issues

| Problem | Solution |
|---------|----------|
| `zrb: command not found` | Ensure `~/.local/bin` (or your Python bin directory) is in your `PATH` |
| `Permission denied` errors | Use `pip install --user zrb` or run install script without `sudo` |
| Python version too old | Zrb requires Python 3.11+. Check with `python --version` |
| `pip not found` | Install pip: `python -m ensurepip --upgrade` or use install script |
| Docker container exits immediately | Add `-it` flags: `docker run -it ...` |
| Module not found errors | Reinstall: `pip uninstall zrb && pip install zrb` |

### Platform-Specific Issues

**Windows:**
```powershell
# If PowerShell execution policy blocks scripts
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# If pip is not recognized
python -m pip install zrb
```

**macOS (Apple Silicon):**
```bash
# If you see architecture warnings
arch -arm64 pip install zrb

# For Docker on Apple Silicon
docker run --platform linux/amd64 ...
```

**Linux:**
```bash
# If you get SSL certificate errors
pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org zrb
```

### Getting Help

If you're still having trouble:
-   Check [GitHub Issues](https://github.com/state-alchemists/zrb/issues) for similar problems
-   Open a new issue with your OS, Python version, and full error message
-   Join discussions on [GitHub Discussions](https://github.com/state-alchemists/zrb/discussions)

---

## 8. General Configuration

Zrb's behavior can be customized further using environment variables. This includes everything from logging levels to default editors and web UI settings. For a complete, exhaustive list of all configurable environment variables, please refer to the dedicated configuration guides:

-   [Environment Variables & Overrides](../configuration/env-vars.md)
-   [LLM & Rate Limiter Configuration](../configuration/llm-config.md)