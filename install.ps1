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
    # Try python first, then py launcher
    if (Command-Exists "python") {
        $script:PY_CMD = "python"
    }
    elseif (Command-Exists "py") {
        # py launcher on Windows -- use it to find Python
        $script:PY_CMD = "py"
    }
    else {
        if (-not (Confirm "Python is not installed. Download from python.org now?")) {
            Warn @"

Python 3.11+ is required. Install it via one of these options:

  Option 1 - winget (recommended):
    winget install Python.Python.3.13

  Option 2 - Download from python.org:
    https://www.python.org/downloads/

  Option 3 - Microsoft Store:
    Search for "Python 3.13"

After installing, restart PowerShell and run this script again.
"@
            exit 1
        }

        # Try winget first
        if (Command-Exists "winget") {
            Log-Info "Installing Python 3.13 via winget..."
            winget install Python.Python.3.13 --accept-source-agreements
        }
        else {
            # Fallback: open the download page
            Start-Process "https://www.python.org/downloads/"
            Warn "Please download and install Python 3.11+ from the opened page, then re-run this script."
            exit 1
        }

        # Refresh PATH and retry
        $env:PATH = [Environment]::GetEnvironmentVariable("PATH", "Machine") + ";" + `
                    [Environment]::GetEnvironmentVariable("PATH", "User") + ";" + $env:PATH

        if (Command-Exists "python") {
            $script:PY_CMD = "python"
        }
        elseif (Command-Exists "py") {
            $script:PY_CMD = "py"
        }
        else {
            Warn "Python was installed but is not on PATH. Restart PowerShell and re-run this script."
            exit 1
        }
    }

    # Verify version
    $versionLine = & $script:PY_CMD -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>&1
    $pythonVersion = $versionLine.Trim()
    Log-Info "Detected Python $pythonVersion"

    $ok = $pythonVersion -match "^3\.(1[1-4])(\..*)?$"  # 3.11-3.14
    if (-not $ok) {
        Warn "Python $pythonVersion detected. Need >=3.11, <3.15."
        if (Confirm "Install Python 3.13 via winget instead?") {
            winget install Python.Python.3.13 --accept-source-agreements
            # Re-check after install
            $env:PATH = [Environment]::GetEnvironmentVariable("PATH", "Machine") + ";" + `
                        [Environment]::GetEnvironmentVariable("PATH", "User") + ";" + $env:PATH
            if (Command-Exists "python") {
                $script:PY_CMD = "python"
            }
            else {
                $script:PY_CMD = "py"
            }
        }
        else {
            exit 1
        }
    }

    Log-OK "Python $pythonVersion"

    # Resolve 'py' launcher to actual Python executable for pipx --python
    if ($script:PY_CMD -eq "py") {
        $script:PY_CMD = & py -c "import sys; print(sys.executable)"
    }
}

#########################################################################################
# pipx Installation
#########################################################################################

function Find-PipxPath {
    # Find pipx.exe in the Python user Scripts folder and add to session PATH
    $pipxDir = Get-ChildItem "$env:USERPROFILE\AppData\Roaming\Python\*\Scripts\pipx.exe" -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty DirectoryName -First 1
    if (-not $pipxDir) {
        $pipxDir = Get-ChildItem "$env:LOCALAPPDATA\pip\Scripts\pipx.exe" -ErrorAction SilentlyContinue |
            Select-Object -ExpandProperty DirectoryName -First 1
    }
    if ($pipxDir -and ($env:PATH -notlike "*$pipxDir*")) {
        $env:PATH = "$pipxDir;$env:PATH"
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

function Pipx-Install-Zrb {
    pipx uninstall zrb -y 2>$null | Out-Null
    & { $env:PIP_PRE=1; pipx install --python $script:PY_CMD zrb }
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
    # Remove stale ~\.local-venv from old-style installations
    $venvPath = "$env:USERPROFILE\.local-venv"
    if (Test-Path $venvPath) {
        Log-Info "Removing old .local-venv directory (migrated to pipx)"
        Remove-Item -Recurse -Force $venvPath
        Log-OK "Removed ~\.local-venv"
    }

    # Strip old .local-venv activation block from PowerShell profile
    if (Test-Path $PROFILE) {
        $lines = Get-Content $PROFILE
        $inBlock = $false
        $filtered = @()
        foreach ($line in $lines) {
            if ($line -match '# Zrb local venv configuration') {
                $inBlock = $true
                continue
            }
            if ($inBlock) {
                if ($line -match '^\s*\}') {
                    $inBlock = $false
                }
                continue
            }
            $filtered += $line
        }
        if ($filtered.Count -ne $lines.Count) {
            Log-Info "Removing old .local-venv activation from PowerShell profile"
            Set-Content $PROFILE -Value $filtered
            Log-OK "Cleaned PowerShell profile"
        }
    }
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

# -- Detect legacy pip installation (pipx is now available for the check) --
if ((Command-Exists "zrb") -and (-not (Test-ZrbInPipx))) {
    Warn "Detected zrb installed via pip (legacy). The script now uses pipx."
    Warn "The legacy package will be auto-removed after the pipx install completes."
}

# -- Step 3: zrb --
Install-Zrb

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
