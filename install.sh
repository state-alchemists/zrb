#!/bin/sh
set -e

#########################################################################################
# Functions
#########################################################################################

command_exists() {
    command -v "$1" >/dev/null 2>&1
}

log_info() {
    if command_exists printf; then
        printf "🤖 \033[0;33m%s\033[0m\n" "$1"
    else
        echo "🤖 $1"
    fi
}

log_ok() {
    if command_exists printf; then
        printf "✅ \033[0;32m%s\033[0m\n" "$1"
    else
        echo "✅ $1"
    fi
}

warn() {
    if command_exists printf; then
        printf "⚠️  \033[0;31m%s\033[0m\n" "$1" >&2
    else
        echo "⚠️  $1" >&2
    fi
}

confirm() {
    [ "$AUTO_YES" = "1" ] && return 0
    log_info "$1 (y/N)"
    read choice
    case "$choice" in y|Y) return 0;; *) return 1;; esac
}

try_sudo() {
    if command_exists sudo; then
        sudo "$@"
    else
        "$@"
    fi
}

#########################################################################################
# Python Installation (via pyenv)
#########################################################################################

register_pyenv() {
    log_info "Registering Pyenv to $1"
    {
        echo 'if [ -d "${HOME}/.pyenv" ]; then'
        echo '    export PYENV_ROOT="$HOME/.pyenv"'
        echo '    export PATH="$PYENV_ROOT/bin:$PATH"'
        echo '    eval "$(pyenv init --path)"'
        echo 'fi'
    } >> "$1"
}

install_pyenv() {
    log_info "Installing pyenv"
    curl https://pyenv.run | bash

    for rc in "$HOME/.zshrc" "$HOME/.bashrc"; do
        [ -f "$rc" ] && register_pyenv "$rc"
    done

    export PYENV_ROOT="$HOME/.pyenv"
    export PATH="$PYENV_ROOT/bin:$PATH"
    eval "$(pyenv init -)" 2>/dev/null || true
    eval "$(pyenv virtualenv-init -)" 2>/dev/null || true
}

install_python_on_pyenv() {
    log_info "Installing Python 3.13.0 via pyenv"
    pyenv install 3.13.0
    pyenv global 3.13.0
    log_ok "Python 3.13.0 installed"
}

install_pyenv_dependencies() {
    OS_TYPE=$(uname)
    if [ "$OS_TYPE" = "Darwin" ]; then
        if command_exists brew; then
            log_info "Installing pyenv build dependencies via brew"
            brew install openssl readline sqlite3 xz zlib tcl-tk
        fi
    elif [ "$OS_TYPE" = "Linux" ] || [ "$OS_TYPE" = "FreeBSD" ]; then
        if command_exists apt; then
            log_info "Installing pyenv build dependencies via apt"
            try_sudo apt update -qq
            try_sudo apt install -y -qq build-essential libssl-dev zlib1g-dev \
                libbz2-dev libreadline-dev libsqlite3-dev curl \
                libncursesw5-dev xz-utils tk-dev libxml2-dev libxmlsec1-dev libffi-dev liblzma-dev
        elif command_exists pacman; then
            log_info "Installing pyenv build dependencies via pacman"
            try_sudo pacman -Syu --noconfirm base-devel openssl zlib xz tk
        elif command_exists dnf; then
            log_info "Installing pyenv build dependencies via dnf"
            try_sudo dnf install -y make gcc patch zlib-devel bzip2 bzip2-devel \
                readline-devel sqlite sqlite-devel openssl-devel tk-devel \
                libffi-devel xz-devel libuuid-devel gdbm-libs libnsl2
        elif command_exists yum; then
            log_info "Installing pyenv build dependencies via yum"
            try_sudo yum install -y gcc make patch zlib-devel bzip2 bzip2-devel \
                readline-devel sqlite sqlite-devel openssl-devel tk-devel libffi-devel xz-devel
        elif command_exists apk; then
            log_info "Installing pyenv build dependencies via apk"
            try_sudo apk add --no-cache git bash build-base libffi-dev openssl-dev \
                bzip2-dev zlib-dev xz-dev readline-dev sqlite-dev tk-dev
        elif command_exists pkg; then
            log_info "Installing pyenv build dependencies via pkg"
            try_sudo pkg update
            try_sudo pkg install -y build-essential
        fi
    fi
}

ensure_python() {
    if command_exists python3; then
        # Use python3 if found, alias it
        PY_CMD="python3"
    elif command_exists python; then
        PY_CMD="python"
    else
        if confirm "Python is not installed. Install it via pyenv?"; then
            install_pyenv_dependencies
            install_pyenv
            PY_CMD="python"
        else
            warn "Python is required. Install Python 3.11+ from https://python.org then re-run this script."
            exit 1
        fi
    fi

    if ! command_exists "$PY_CMD"; then
        # pyenv was installed but python wasn't compiled yet
        if command_exists pyenv; then
            install_python_on_pyenv
            PY_CMD="python"
        else
            warn "Python is not available after installation attempt."
            exit 1
        fi
    fi

    # Verify Python version
    PYTHON_VERSION=$("$PY_CMD" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    log_info "Detected Python $PYTHON_VERSION"
    case "$PYTHON_VERSION" in
        3.11|3.12|3.13|3.14) log_ok "Python $PYTHON_VERSION" ;;
        3.*)
            warn "Python $PYTHON_VERSION detected. Need >=3.11, <3.15."
            if confirm "Install Python 3.13 via pyenv instead?"; then
                install_pyenv_dependencies
                install_pyenv
                install_python_on_pyenv
                PY_CMD="python"
            else
                exit 1
            fi
            ;;
        *) warn "Unknown Python version. Need >=3.11, <3.15."; exit 1 ;;
    esac
}

#########################################################################################
# pipx Installation
#########################################################################################

ensure_pipx() {
    if command_exists pipx; then
        log_ok "pipx already installed"
        return
    fi

    log_info "Installing pipx"

    OS_TYPE=$(uname)

    # macOS: brew is the cleanest path
    if [ "$OS_TYPE" = "Darwin" ] && command_exists brew; then
        brew install pipx
        log_ok "pipx installed via brew"
        return
    fi

    # Linux/FreeBSD: distro packages where available
    if [ "$OS_TYPE" = "Linux" ] || [ "$OS_TYPE" = "FreeBSD" ]; then
        if command_exists apt; then
            try_sudo apt install -y -qq pipx 2>/dev/null && { log_ok "pipx installed via apt"; return; }
        fi
        if command_exists pacman; then
            try_sudo pacman -S --noconfirm python-pipx 2>/dev/null && { log_ok "pipx installed via pacman"; return; }
        fi
        if command_exists dnf; then
            try_sudo dnf install -y pipx 2>/dev/null && { log_ok "pipx installed via dnf"; return; }
        fi
        if command_exists pkg; then
            try_sudo pkg install -y py-pipx 2>/dev/null && { log_ok "pipx installed via pkg"; return; }
        fi
    fi

    # Universal fallback: pip install --user
    "$PY_CMD" -m pip install --user pipx -q

    # Add ~/.local/bin to PATH for this session (pip's user install location)
    export PATH="$HOME/.local/bin:$PATH"

    if ! command_exists pipx; then
        warn "pipx installation failed. Check the error above."
        exit 1
    fi

    log_ok "pipx installed via pip"
}

ensure_pipx_path() {
    # pipx ensurepath writes to shell rc files
    if command_exists pipx; then
        pipx ensurepath >/dev/null 2>&1 || true
        log_ok "pipx added to PATH"
    fi
}

#########################################################################################
# Zrb Installation
#########################################################################################

install_zrb() {
    if pipx list --short 2>/dev/null | grep -q "^zrb "; then
        log_info "Upgrading zrb via pipx..."
        PIP_PRE=1 pipx upgrade zrb
    elif command_exists zrb; then
        warn "zrb was installed via pip (legacy) — migrating to pipx"
        PIP_PRE=1 pipx install zrb
        # Auto-clean legacy install to avoid PATH conflict (fix #6)
        pip uninstall zrb -y 2>/dev/null || true
    else
        log_info "Installing zrb via pipx..."
        PIP_PRE=1 pipx install zrb
    fi
    log_ok "zrb installed — run 'zrb --help' to get started"
}

register_autocomplete() {
    if command_exists zrb; then
        for rc in "$HOME/.zshrc" "$HOME/.bashrc"; do
            [ -f "$rc" ] || continue
            shell_name=$(basename "$rc" | sed 's/\.//')
            if ! grep -q "zrb shell autocomplete" "$rc" 2>/dev/null; then
                log_info "Registering zrb autocomplete to $rc"
                {
                    echo ""
                    echo "# Zrb autocomplete"
                    echo "if command_exists zrb; then"
                    echo "    eval \"\$(zrb shell autocomplete $shell_name)\""
                    echo "fi"
                } >> "$rc"
            fi
        done
        log_ok "Autocomplete registered"
    fi
}

cleanup_local_venv() {
    # Remove stale ~/.local-venv from old-style installations
    if [ -d "$HOME/.local-venv" ]; then
        log_info "Removing old ~/.local-venv directory (migrated to pipx)"
        rm -rf "$HOME/.local-venv"
        log_ok "Removed ~/.local-venv"
    fi

    # Strip old .local-venv activation blocks from shell rc files
    for rc in "$HOME/.zshrc" "$HOME/.bashrc"; do
        [ -f "$rc" ] || continue
        if grep -q "local-venv" "$rc" 2>/dev/null; then
            log_info "Removing old .local-venv activation from $(basename "$rc")"
            # Remove the if-block that activates .local-venv (written by old install.sh)
            if command_exists sed; then
                sed '/^if \[ -f "${HOME}\/.local-venv\/bin\/activate" \]/,/^fi$/d' "$rc" > "${rc}.tmp"
                mv "${rc}.tmp" "$rc"
            fi
            log_ok "Cleaned $(basename "$rc")"
        fi
    done
}

#########################################################################################
# LSP Servers (optional)
#########################################################################################

install_lsps() {
    if ! command_exists npm && ! command_exists go && ! command_exists rustup; then
        log_info "No JS/Go/Rust toolchains detected — only Python LSP will be installed."
    fi

    log_info "Installing python-lsp-server (pylsp)"
    pipx inject zrb 'python-lsp-server[all]'

    if command_exists npm && confirm "Install typescript-language-server (for JS/TS)?"; then
        npm install -g typescript-language-server typescript
    fi
    if command_exists go && confirm "Install gopls (for Go)?"; then
        go install golang.org/x/tools/gopls@latest
    fi
    if command_exists rustup && confirm "Install rust-analyzer (for Rust)?"; then
        rustup component add rust-analyzer
    fi

    log_ok "LSP servers installed. zrb auto-detects which ones are on PATH."
}

#########################################################################################
# Termux Setup
#########################################################################################

setup_termux() {
    log_info "Setting environment variables"
    export CFLAGS="-Wno-incompatible-function-pointer-types"

    log_info "Updating repos and packages"
    termux-change-repo
    pkg update -y
    pkg upgrade -y

    if [ ! -d "${HOME}/storage" ]; then
        log_info "Setting up storage"
        termux-setup-storage
    fi

    log_info "Installing prerequisites"
    pkg install -y python clang cmake build-essential rust golang \
        binutils ninja patchelf libxml2 libxslt curl wget git which \
        swig postgresql sqlite termux-api openssh
}

#########################################################################################
# Main
#########################################################################################

# Parse flags
AUTO_YES=0
for arg in "$@"; do
    case "$arg" in
        -y|--yes) AUTO_YES=1 ;;
    esac
done

# Detect Termux
if [ -n "$PREFIX" ] && [ "$PREFIX" = "/data/data/com.termux/files/usr" ]; then
    IS_TERMUX=1
else
    IS_TERMUX=0
fi

# Banner
cat << 'EOF'

    ╔════════════════════════════╗
    ║  Zrb — Your Automation     ║
    ║        Powerhouse          ║
    ╚════════════════════════════╝

EOF

# ── Migrate from legacy pip/poetry/local-venv installation ──
if command_exists zrb && ! pipx list --short 2>/dev/null | grep -q "^zrb "; then
    warn "Detected zrb installed via pip (legacy). The script now uses pipx."
    warn "Your existing installation will be shadowed by the new pipx install."
    warn "The legacy package will be auto-removed after the pipx install completes."
fi

# ── Step 1: Termux setup (if applicable) ──
if [ "$IS_TERMUX" = "1" ] && confirm "Set up Termux for zrb?"; then
    setup_termux
fi

# ── Step 2: Ensure Python ──
ensure_python

# ── Step 3: pipx ──
ensure_pipx
ensure_pipx_path

# ── Step 4: zrb ──
install_zrb

# ── Step 5: Clean up legacy .local-venv ──
cleanup_local_venv

# ── Step 6: Autocomplete ──
register_autocomplete

# ── Step 7: LSP servers ──
if confirm "Install LSP servers for richer code diagnostics?"; then
    install_lsps
fi

log_ok "Installation complete! Restart your terminal or run 'exec \$SHELL' to pick up the new PATH."
