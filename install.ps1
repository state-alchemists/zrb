# PowerShell installation script for Zrb on Windows
# Equivalent to install.sh for Unix systems

$ErrorActionPreference = "Stop"

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

function Confirm {
    param([string]$Prompt)
    Log-Info "$Prompt (y/N)"
    $choice = Read-Host
    switch -Regex ($choice) {
        "^[yY]" { return $true }
        "^[nN]" { return $false }
        default {
            Write-Host "Invalid choice"
            return $false
        }
    }
}

function Add-PathPermanent {
    param([string]$Path)
    $userPath = [Environment]::GetEnvironmentVariable("PATH", "User")
    if ($userPath -notlike "*$Path*") {
        [Environment]::SetEnvironmentVariable("PATH", "$Path;$userPath", "User")
        $env:PATH = "$Path;$env:PATH"
    }
}

function Register-LocalVenv {
    param([string]$ProfilePath)

    Log-Info "Registering .local-venv to $ProfilePath"

    # Ensure profile directory exists
    $profileDir = Split-Path -Parent $ProfilePath
    if ($profileDir -and -not (Test-Path $profileDir)) {
        New-Item -ItemType Directory -Path $profileDir -Force | Out-Null
    }

    $venvBlock = @"

# Zrb local venv configuration
if (Test-Path "`$HOME\.local-venv\Scripts\Activate.ps1") {
    . "`$HOME\.local-venv\Scripts\Activate.ps1"
}
"@

    if (-not (Test-Path $ProfilePath)) {
        New-Item -ItemType File -Path $ProfilePath -Force | Out-Null
    }

    if (-not (Select-String -Path $ProfilePath -Pattern "local-venv" -Quiet)) {
        Add-Content -Path $ProfilePath -Value $venvBlock
    }
}

function Create-And-Register-LocalVenv {
    Log-Info "Creating local venv at $HOME\.local-venv"
    python -m venv "$HOME\.local-venv"
    & "$HOME\.local-venv\Scripts\Activate.ps1"

    # Register to PowerShell profile
    Register-LocalVenv $PROFILE
    Log-Info "Virtual environment created and activated"
}

function Install-Poetry {
    Log-Info "Installing Poetry"
    python -m pip install --upgrade pip setuptools --quiet
    python -m pip install poetry --quiet

    # Poetry installs to user scripts, ensure it's in PATH
    $userScripts = "$HOME\.local\bin"
    if (Test-Path $userScripts) {
        Add-PathPermanent $userScripts
    }

    # Also check AppData\local\pip\Scripts on Windows
    $pipScripts = "$env:LOCALAPPDATA\pip\Scripts"
    if (Test-Path $pipScripts) {
        Add-PathPermanent $pipScripts
    }

    Log-Info "Poetry installed"
}

function Install-Zrb {
    Log-Info "Installing Zrb"
    python -m pip install --pre zrb --quiet
    Log-Info "Zrb installed"
}

#########################################################################################
# Main Script
#########################################################################################

# Check if running as administrator (not recommended)
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if ($isAdmin) {
    Log-Info "Warning: Running as Administrator is not recommended."
    Log-Info "Consider running as a regular user."
}

$IsLocalVenvInstalled = $false

# Check for Python
if (-not (Command-Exists "python")) {
    # Try python3 as fallback
    if (Command-Exists "python3") {
        Log-Info "Found python3, creating python alias..."
        Set-Alias -Name python -Value python3 -Scope Global
    } else {
        Log-Info ""
        Log-Info "Python not found!"
        Log-Info ""
        Log-Info "Please install Python first using one of these methods:"
        Log-Info ""
        Log-Info "  Option 1 - winget (recommended):"
        Log-Info "    winget install Python.Python.3.13"
        Log-Info ""
        Log-Info "  Option 2 - Download from python.org:"
        Log-Info "    https://www.python.org/downloads/"
        Log-Info ""
        Log-Info "  Option 3 - Microsoft Store:"
        Log-Info "    Search for 'Python 3.13' in Microsoft Store"
        Log-Info ""
        Log-Info "After installing Python, restart PowerShell and run this script again."
        exit 1
    }
}

# Get Python version
$pythonVersion = python --version 2>&1
Log-Info "Detected: $pythonVersion"

# Offer Poetry
if (-not (Command-Exists "poetry") -and (Confirm "Do you want to install Poetry?")) {
    Install-Poetry
}

# Offer virtual environment
if (-not (Test-Path "$HOME\.local-venv") -and (Confirm "Do you want to create a virtual environment at ~/.local-venv?")) {
    Create-And-Register-LocalVenv
    $IsLocalVenvInstalled = $true
}

# Install Zrb
if (-not (Command-Exists "zrb")) {
    Install-Zrb
}

# Final message
Write-Host ""
Log-Info "Installation complete!"
Write-Host ""

if ($IsLocalVenvInstalled) {
    Log-Info "IMPORTANT: You need to restart your terminal session!"
    Log-Info "After restart, run: zrb --help"
} else {
    Log-Info "Run: zrb --help"
}

Write-Host ""
Log-Info "Documentation: https://github.com/state-alchemists/zrb"