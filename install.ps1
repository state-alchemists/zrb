#!/usr/bin/env pwsh
# PowerShell installation script for Zrb on Windows
# Usage: .\install.ps1 [-Yes]

param(
    [switch]$Yes
)

$AUTO_YES = $Yes.IsPresent

#########################################################################################
# Functions
#########################################################################################

function Command-Exists {
    param([string]$Command)
    $null -ne (Get-Command $Command -ErrorAction SilentlyContinue)
}

function Log-Info {
    param([string]$Message)
    Write-Host "🤖 " -NoNewline
    Write-Host $Message -ForegroundColor Yellow
}

function Log-OK {
    param([string]$Message)
    Write-Host "✅ " -NoNewline
    Write-Host $Message -ForegroundColor Green
}

function Warn {
    param([string]$Message)
    Write-Host "⚠️  " -NoNewline
    Write-Host $Message -ForegroundColor Red
}

function Confirm {
    param([string]$Prompt)
    if ($AUTO_YES) { return $true }
    Log-Info "$Prompt (y/N)"
    $choice = Read-Host
    return ($choice -match "^[yY]")
}

#########################################################################################
# Python Detection & Installation
#########################################################################################

function Ensure-Python {
    # zrb defaults to Python 3.13 for every install so pipx's resolution stays
    # reproducible across machines -- see Ensure-PipxDefaultPython for why.
    if (Command-Exists "py") {
        $resolved = & py -3.13 -c "import sys; print(sys.executable)" 2>$null
        if ($LASTEXITCODE -eq 0 -and $resolved) {
            $script:PY_CMD = $resolved.Trim()
            Log-OK "Found Python 3.13"
            return
        }
    }

    $installed = $false
    if (Confirm "Python 3.13 is not installed. Install it now?") {
        if (Command-Exists "winget") {
            Log-Info "Installing Python 3.13 via winget..."
            winget install Python.Python.3.13 --accept-source-agreements
            $installed = $true
        }
        else {
            Start-Process "https://www.python.org/downloads/"
            Warn "Please download and install Python 3.13 from the opened page, then re-run this script."
            exit 1
        }
    }

    if ($installed) {
        $env:PATH = [Environment]::GetEnvironmentVariable("PATH", "Machine") + ";" + `
                    [Environment]::GetEnvironmentVariable("PATH", "User") + ";" + $env:PATH
        if (Command-Exists "py") {
            $resolved = & py -3.13 -c "import sys; print(sys.executable)" 2>$null
            if ($resolved) {
                $script:PY_CMD = $resolved.Trim()
                Log-OK "Installed Python 3.13"
                return
            }
        }
        Warn "Python 3.13 was installed but is not on PATH. Restart PowerShell and re-run this script."
        exit 1
    }

    # Fall back to whatever compatible interpreter is already on PATH
    if (Command-Exists "python") {
        $script:PY_CMD = "python"
    }
    elseif (Command-Exists "py") {
        $script:PY_CMD = (& py -c "import sys; print(sys.executable)").Trim()
    }
    else {
        Warn "Python 3.11+ is required. Install it from https://www.python.org/downloads/ then re-run this script."
        exit 1
    }

    $pythonVersion = (& $script:PY_CMD -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>&1).Trim()
    if ($pythonVersion -notmatch "^3\.(1[1-4])(\..*)?$") {
        Warn "Python $pythonVersion detected. Need >=3.11, <3.15."
        exit 1
    }
    Log-OK "Using Python $pythonVersion"
}

#########################################################################################
# pipx Installation
#########################################################################################

function Find-PipxPath {
    # Find pipx.exe in the Python user Scripts folder and add to session + permanent PATH.
    # `pipx ensurepath` only persists pipx's managed bin dir, not pipx.exe's own
    # location, so without this a new PowerShell window can't find `pipx` itself.
    $pipxDir = Get-ChildItem "$env:USERPROFILE\AppData\Roaming\Python\*\Scripts\pipx.exe" -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty DirectoryName -First 1
    if (-not $pipxDir) {
        $pipxDir = Get-ChildItem "$env:LOCALAPPDATA\pip\Scripts\pipx.exe" -ErrorAction SilentlyContinue |
            Select-Object -ExpandProperty DirectoryName -First 1
    }
    if (-not $pipxDir) { return }

    if ($env:PATH -notlike "*$pipxDir*") {
        $env:PATH = "$pipxDir;$env:PATH"
    }

    $userPath = [Environment]::GetEnvironmentVariable("PATH", "User")
    if ($userPath -notlike "*$pipxDir*") {
        [Environment]::SetEnvironmentVariable("PATH", "$userPath;$pipxDir", "User")
    }
}

function Ensure-Pipx {
    if (Command-Exists "pipx") {
        Log-OK "pipx already installed"
        return
    }

    Log-Info "Installing pipx"

    # Scoop is the cleanest on Windows
    if (Command-Exists "scoop") {
        scoop install pipx
        Log-OK "pipx installed via Scoop"
        return
    }

    # Fallback: pip install
    $pipUserFlag = if ($env:VIRTUAL_ENV) { "" } else { "--user" }
    & $script:PY_CMD -m pip install $pipUserFlag pipx -q
    if ($LASTEXITCODE -ne 0) {
        if ($pipUserFlag -eq "") {
            Warn "pipx installation failed. Deactivate your virtualenv and re-run, or install via: scoop install pipx"
        } else {
            Warn "pipx installation failed. Try: scoop install pipx"
        }
        exit 1
    }

    Find-PipxPath
    Log-OK "pipx installed via pip"
}

function Ensure-PipxPath {
    if (Command-Exists "pipx") {
        pipx ensurepath > $null 2>&1
        Log-OK "pipx added to PATH"
    } else {
        # pipx may have been removed from PATH by Cleanup-LocalVenv
        Find-PipxPath
        if (Command-Exists "pipx") {
            Log-OK "pipx restored to PATH"
        }
    }
}

function Ensure-PipxDefaultPython {
    # Bare `pipx reinstall`/`pipx upgrade` (no --python flag) default to whatever
    # interpreter pipx itself runs on -- which can be a stale Python tied to
    # pipx's own installation, silently resolving zrb to an old release that
    # still supports it. Pin PIPX_DEFAULT_PYTHON so those commands keep
    # targeting a Python new enough for zrb even when run outside this script.
    [Environment]::SetEnvironmentVariable("PIPX_DEFAULT_PYTHON", $script:PY_CMD, "User")
    $env:PIPX_DEFAULT_PYTHON = $script:PY_CMD
    Log-OK "Pinned PIPX_DEFAULT_PYTHON to $script:PY_CMD"
}

#########################################################################################
# Zrb Installation
#########################################################################################

function Test-ZrbInPipx {
    # pipx list --short writes "nothing has been installed" to stderr on PS 5.1
    # which becomes an ugly error message. Use --json for clean output.
    $json = pipx list --json 2>$null
    if (-not $json) { return $false }
    try {
        $parsed = $json | ConvertFrom-Json
        return [bool]($parsed.venvs.PSObject.Properties.Name -contains "zrb")
    } catch {
        return $false
    }
}

function Confirm-Extras {
    if (Confirm "Install all optional dependencies (RAG, Playwright, voice input, and every LLM provider SDK)?") {
        $script:ZrbExtras = "[rag,playwright,cohere,vertexai,google,anthropic,groq,mistral,xai,bedrock,huggingface,voyageai,voice,python]"
        Log-OK "Will install zrb with all optional extras"
    }
}

function Pipx-Install-Zrb {
    # `pipx uninstall` takes no -y/--yes flag; passing one errors out silently
    # (swallowed below), leaving the old venv in place so the install that
    # follows hits pipx's "already installed" guard and does nothing.
    pipx uninstall zrb 2>$null | Out-Null
    # --pip-args (not the PIP_PRE env var) persists in pipx's metadata, so later
    # `pipx upgrade`/`pipx reinstall` keep tracking pre-releases automatically.
    pipx install --pip-args='--pre' --python $script:PY_CMD "zrb$($script:ZrbExtras)"
}

function Install-Zrb {
    if (Test-ZrbInPipx) {
        # Uninstall + fresh install so --python takes effect (pipx ignores --python with --force)
        Pipx-Install-Zrb
    }
    elseif (Command-Exists "zrb") {
        Warn "zrb was installed via pip (legacy) -- migrating to pipx"
        Pipx-Install-Zrb
        if ($LASTEXITCODE -eq 0) {
            # Auto-clean legacy install to avoid PATH conflict (fix #6)
            pip uninstall zrb -y -q 2>$null
        }
    }
    else {
        Log-Info "Installing zrb via pipx..."
        Pipx-Install-Zrb
    }

    if (Command-Exists "zrb") {
        Log-OK "zrb installed -- run 'zrb --help' to get started"
    }
    else {
        Warn "zrb installation failed. Check the error above."
        exit 1
    }
}

function Expose-PythonTools {
    # pipx only exposes the main package's entry points on PATH; black/isort
    # pulled in by the [python] extra stay buried inside the zrb venv.
    # Re-inject them with --include-apps so their binaries land on PATH.
    if ($script:ZrbExtras -notmatch "python") { return }
    Log-Info "Exposing black and isort on PATH"
    pipx inject zrb black isort --include-apps 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Log-OK "black and isort exposed"
    }
    else {
        Warn "Could not expose black/isort binaries (non-fatal). Run: pipx inject zrb black isort --include-apps"
    }
}

function Register-Autocomplete {
    if (-not (Command-Exists "zrb")) { return }

    $profileDir = Split-Path -Parent $PROFILE
    if ($profileDir -and -not (Test-Path $profileDir)) {
        New-Item -ItemType Directory -Path $profileDir -Force | Out-Null
    }

    $autocompleteBlock = @"

# Zrb autocomplete
if (Get-Command zrb -ErrorAction SilentlyContinue) {
    Invoke-Expression ((& zrb shell autocomplete powershell) -join "`n")
}
"@

    if (-not (Test-Path $PROFILE)) {
        New-Item -ItemType File -Path $PROFILE -Force | Out-Null
    }

    if (-not (Select-String -Path $PROFILE -Pattern "zrb shell autocomplete" -Quiet)) {
        Log-Info "Registering zrb autocomplete to $PROFILE"
        Add-Content -Path $PROFILE -Value $autocompleteBlock
        Log-OK "Autocomplete registered"
    } else {
        # Fix existing entry that uses broken '& zrb shell autocomplete' (returns Object[])
        $profileContent = Get-Content $PROFILE -Raw
        $oldLine = 'Invoke-Expression (& zrb shell autocomplete powershell)'
        $newLine = 'Invoke-Expression ((& zrb shell autocomplete powershell) -join "`n")'
        if ($profileContent -match [regex]::Escape($oldLine)) {
            $profileContent = $profileContent -replace [regex]::Escape($oldLine), $newLine
            Set-Content $PROFILE -Value $profileContent
            Log-OK "Fixed existing autocomplete entry in PowerShell profile"
        }
    }
}

function Cleanup-LocalVenv {
    # Uninstall zrb from old-style .local-venv so the pipx version takes precedence
    $venvPath = "$env:USERPROFILE\.local-venv"
    if (Test-Path "$venvPath\Scripts\pip.exe") {
        Log-Info "Uninstalling old zrb from ~\.local-venv (migrated to pipx)"
        & "$venvPath\Scripts\pip.exe" uninstall zrb -y -q 2>$null
        Log-OK "Uninstalled old zrb from ~\.local-venv"
    }
    if (Test-Path $venvPath) {
        Log-Info "~\.local-venv is no longer needed. Remove it with: Remove-Item -Recurse -Force ~\.local-venv"
    }
    # The old activation block in PowerShell profile is guarded by Test-Path and harmless.
    # No profile changes needed.
}

#########################################################################################
# LSP Servers (optional)
#########################################################################################

function Install-Lsps {
    # Python LSP is always installed -- zrb itself is Python
    if (-not (Command-Exists "npm") -and -not (Command-Exists "go") -and -not (Command-Exists "rustup")) {
        Log-Info "No JS/Go/Rust toolchains detected -- only Python LSP will be installed."
    }
    Log-Info "Installing python-lsp-server (pylsp)"
    pipx inject zrb 'python-lsp-server[all]' 2>$null
    if ($LASTEXITCODE -ne 0) {
        Warn "LSP server install failed (non-fatal)"
    }

    if ((Command-Exists "npm") -and (Confirm "Install typescript-language-server (for JS/TS)?")) {
        npm install -g typescript-language-server typescript
    }
    if ((Command-Exists "go") -and (Confirm "Install gopls (for Go)?")) {
        go install golang.org/x/tools/gopls@latest
    }
    if ((Command-Exists "rustup") -and (Confirm "Install rust-analyzer (for Rust)?")) {
        rustup component add rust-analyzer
    }

    Log-OK "LSP servers installed. zrb auto-detects which ones are on PATH."
}

#########################################################################################
# Main
#########################################################################################

# Banner
Write-Host @"

    ╔════════════════════════════╗
    ║  Zrb — Your Automation     ║
    ║        Powerhouse          ║
    ╚════════════════════════════╝

"@

# -- Admin check --
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if ($isAdmin) {
    Warn "Running as Administrator is not recommended. Run as a regular user if possible."
}

# -- Step 1: Ensure Python --
Ensure-Python

# -- Step 2: pipx --
Ensure-Pipx
Ensure-PipxPath
Ensure-PipxDefaultPython

# -- Detect legacy pip installation (pipx is now available for the check) --
if ((Command-Exists "zrb") -and (-not (Test-ZrbInPipx))) {
    Warn "Detected zrb installed via pip (legacy). The script now uses pipx."
    Warn "The legacy package will be auto-removed after the pipx install completes."
}

# -- Step 3: zrb --
$script:ZrbExtras = ""
Confirm-Extras
Install-Zrb
Expose-PythonTools

# -- Step 4: Clean up legacy .local-venv --
Cleanup-LocalVenv

# -- pipx may have been in .local-venv\Scripts, re-add to PATH --
Ensure-PipxPath

# -- Step 5: Autocomplete --
Register-Autocomplete

# -- Step 6: LSP servers --
if (Confirm "Install LSP servers for richer code diagnostics?") {
    Install-Lsps
}

Write-Host ""
Log-OK "Installation complete! Restart your terminal to pick up the new PATH."
