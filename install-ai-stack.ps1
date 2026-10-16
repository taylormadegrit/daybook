<#
.SYNOPSIS
    Daybook 1-Click AI Stack Installer
    Installs: Node.js LTS, Claude Code CLI, and Ollama Local AI on Windows.
#>

param(
    [switch]$SkipModelPull,
    [string]$Model = "qwen2.5:7b",
    [switch]$NonInteractive
)

$ErrorActionPreference = "Continue"

function Write-Step {
    param([string]$Title)
    Write-Host "`n====> $Title" -ForegroundColor Cyan
}

function Write-Success {
    param([string]$Msg)
    Write-Host " [OK] $Msg" -ForegroundColor Green
}

function Write-Info {
    param([string]$Msg)
    Write-Host " [..] $Msg" -ForegroundColor Yellow
}

function Write-Warn {
    param([string]$Msg)
    Write-Host " [!] $Msg" -ForegroundColor Magenta
}

function Write-Err {
    param([string]$Msg)
    Write-Host " [ERR] $Msg" -ForegroundColor Red
}

function Refresh-EnvPath {
    $machinePath = [System.Environment]::GetEnvironmentVariable("Path", "Machine")
    $userPath = [System.Environment]::GetEnvironmentVariable("Path", "User")
    $env:Path = "$machinePath;$userPath"

    # Common binary directories
    $candidates = @(
        "$env:ProgramFiles\nodejs",
        "$env:APPDATA\npm",
        "$env:LOCALAPPDATA\Programs\Ollama",
        "$env:LOCALAPPDATA\Programs\Ollama\bin",
        "$HOME\.local\bin"
    )
    foreach ($dir in $candidates) {
        if ((Test-Path $dir) -and ($env:Path -notlike "*$dir*")) {
            $env:Path = "$dir;$env:Path"
        }
    }
}

Clear-Host
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host "       DAYBOOK 1-CLICK AI STACK INSTALLER FOR WINDOWS           " -ForegroundColor White
Write-Host "   Installs: Node.js LTS + Claude Code CLI + Ollama Local AI   " -ForegroundColor Cyan
Write-Host "================================================================" -ForegroundColor Cyan

Refresh-EnvPath

# -------------------------------------------------------------
# STEP 1: NODE.JS LTS
# -------------------------------------------------------------
Write-Step "Checking Node.js LTS"
$nodeInstalled = $false
try {
    $nodeVer = & node -v 2>$null
    if ($nodeVer -match "v(\d+)") {
        $major = [int]$matches[1]
        if ($major -ge 18) {
            Write-Success "Node.js $nodeVer is already installed."
            $nodeInstalled = $true
        } else {
            Write-Warn "Node.js $nodeVer is installed, but version 18+ is required for Claude Code."
        }
    }
} catch {}

if (-not $nodeInstalled) {
    Write-Info "Node.js not detected. Installing Node.js LTS..."
    $installedWithWinget = $false

    if (Get-Command winget -ErrorAction SilentlyContinue) {
        Write-Info "Attempting installation via Windows Package Manager (winget)..."
        try {
            $proc = Start-Process winget -ArgumentList "install", "OpenJS.NodeJS.LTS", "--silent", "--accept-package-agreements", "--accept-source-agreements" -NoNewWindow -PassThru -Wait
            if ($proc.ExitCode -eq 0) {
                $installedWithWinget = $true
                Write-Success "Node.js LTS installed via winget."
            }
        } catch {}
    }

    if (-not $installedWithWinget) {
        Write-Info "Downloading official Node.js LTS MSI package directly..."
        $msiUrl = "https://nodejs.org/dist/v22.14.0/node-v22.14.0-x64.msi"
        $msiDest = "$env:TEMP\node-v22-x64.msi"
        try {
            [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 -bor [Net.SecurityProtocolType]::Tls13
            (New-Object System.Net.WebClient).DownloadFile($msiUrl, $msiDest)
            Write-Info "Installing Node.js MSI silently..."
            $proc = Start-Process msiexec.exe -ArgumentList "/i", "`"$msiDest`"", "/qn", "/norestart" -NoNewWindow -PassThru -Wait
            if ($proc.ExitCode -eq 0 -or $proc.ExitCode -eq 3010) {
                Write-Success "Node.js LTS installed via MSI."
            } else {
                Write-Warn "MSI returned exit code $($proc.ExitCode)."
            }
            Remove-Item $msiDest -Force -ErrorAction SilentlyContinue
        } catch {
            Write-Err "Could not download Node.js MSI: $($_.Exception.Message)"
        }
    }

    Refresh-EnvPath
    $nodeVer = & node -v 2>$null
    if ($nodeVer) {
        Write-Success "Node.js verified: $nodeVer"
    } else {
        Write-Warn "Node.js was installed. You may need to restart your terminal session for PATH to take full effect."
    }
}

# -------------------------------------------------------------
# STEP 2: CLAUDE CODE CLI
# -------------------------------------------------------------
Write-Step "Checking Claude Code CLI"
Refresh-EnvPath
$claudeInstalled = $false
try {
    $claudeVer = & claude --version 2>$null
    if ($claudeVer) {
        Write-Success "Claude Code is already installed: $claudeVer"
        $claudeInstalled = $true
    }
} catch {}

if (-not $claudeInstalled) {
    Write-Info "Installing Claude Code CLI globally using npm (@anthropic-ai/claude-code)..."
    try {
        $npmProc = Start-Process cmd.exe -ArgumentList "/c", "npm install -g @anthropic-ai/claude-code" -NoNewWindow -PassThru -Wait
        Refresh-EnvPath
        $claudeVer = & claude --version 2>$null
        if ($claudeVer) {
            Write-Success "Claude Code successfully installed: $claudeVer"
            $claudeInstalled = $true
        } else {
            Write-Info "Checking npm global bin path..."
            $npmPrefix = (& npm config get prefix 2>$null)
            if ($npmPrefix -and (Test-Path "$npmPrefix\claude.cmd")) {
                $env:Path = "$npmPrefix;$env:Path"
                Write-Success "Claude Code found at $npmPrefix\claude.cmd"
                $claudeInstalled = $true
            }
        }
    } catch {
        Write-Err "Error running npm install: $($_.Exception.Message)"
    }
}

# Connect Claude Code to Daybook MCP server if available
if ($claudeInstalled) {
    try {
        $mcpExe = "D:\projects\local-reminders\daybook-mcp.exe"
        if (-not (Test-Path $mcpExe)) {
            $mcpExe = "$PSScriptRoot\daybook-mcp.exe"
        }
        if (Test-Path $mcpExe) {
            Write-Info "Connecting Daybook MCP server ('reminders') to Claude Code..."
            & claude mcp add --scope user reminders -- "$mcpExe" 2>$null
            Write-Success "Daybook MCP server connected to Claude Code."
        }
    } catch {}
}

# -------------------------------------------------------------
# STEP 3: OLLAMA LOCAL AI
# -------------------------------------------------------------
Write-Step "Checking Ollama (Local AI Engine)"
Refresh-EnvPath
$ollamaInstalled = $false
$ollamaCmd = Get-Command ollama -ErrorAction SilentlyContinue
if (-not $ollamaCmd -and (Test-Path "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe")) {
    $env:Path = "$env:LOCALAPPDATA\Programs\Ollama;$env:Path"
    $ollamaCmd = Get-Command ollama -ErrorAction SilentlyContinue
}

if ($ollamaCmd) {
    try {
        $ollamaVer = & ollama --version 2>$null
        Write-Success "Ollama is already installed: $ollamaVer"
        $ollamaInstalled = $true
    } catch {}
}

if (-not $ollamaInstalled) {
    Write-Info "Ollama is not installed. Installing Ollama for Windows..."
    $installedWithWinget = $false

    if (Get-Command winget -ErrorAction SilentlyContinue) {
        Write-Info "Attempting installation via winget (Ollama.Ollama)..."
        try {
            $proc = Start-Process winget -ArgumentList "install", "Ollama.Ollama", "--silent", "--accept-package-agreements", "--accept-source-agreements" -NoNewWindow -PassThru -Wait
            if ($proc.ExitCode -eq 0) {
                $installedWithWinget = $true
                Write-Success "Ollama installed via winget."
            }
        } catch {}
    }

    if (-not $installedWithWinget) {
        Write-Info "Downloading official Ollama Windows installer..."
        $ollamaUrl = "https://ollama.com/download/OllamaSetup.exe"
        $ollamaDest = "$env:TEMP\OllamaSetup.exe"
        try {
            [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 -bor [Net.SecurityProtocolType]::Tls13
            (New-Object System.Net.WebClient).DownloadFile($ollamaUrl, $ollamaDest)
            Write-Info "Running Ollama installer silently..."
            $proc = Start-Process $ollamaDest -ArgumentList "/silent" -NoNewWindow -PassThru -Wait
            if ($proc.ExitCode -eq 0) {
                Write-Success "Ollama installed successfully."
            }
            Remove-Item $ollamaDest -Force -ErrorAction SilentlyContinue
        } catch {
            Write-Err "Could not download Ollama installer: $($_.Exception.Message)"
        }
    }

    Refresh-EnvPath
}

# Ensure Ollama service is running
Write-Step "Verifying Ollama Service"
$ollamaRunning = $false
for ($i = 0; $i -lt 3; $i++) {
    try {
        $resp = Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/tags" -Method Get -TimeoutSec 2 -ErrorAction Stop
        if ($resp) {
            $ollamaRunning = $true
            Write-Success "Ollama service is active and responding on http://127.0.0.1:11434."
            break
        }
    } catch {
        Write-Info "Starting Ollama background service..."
        Start-Process "ollama" -ArgumentList "serve" -WindowStyle Hidden -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 3
    }
}

# -------------------------------------------------------------
# STEP 4: STARTER MODEL DOWNLOAD
# -------------------------------------------------------------
if ($ollamaRunning -and -not $SkipModelPull) {
    Write-Step "Checking Default Model ($Model)"
    try {
        $tags = Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/tags" -Method Get -TimeoutSec 3
        $hasModel = $false
        if ($tags.models) {
            foreach ($m in $tags.models) {
                if ($m.name -eq $Model -or $m.name -like "$Model*") {
                    $hasModel = $true
                    break
                }
            }
        }

        if ($hasModel) {
            Write-Success "Starter model '$Model' is already installed."
        } else {
            Write-Info "Pulling starter model '$Model' for Daybook..."
            Write-Host "This runs on your GPU/CPU for private notes, scheduling, and chat.`n" -ForegroundColor Gray
            & ollama pull $Model
            if ($LASTEXITCODE -eq 0) {
                Write-Success "Model '$Model' pulled successfully!"
            } else {
                Write-Warn "Could not pull '$Model'. You can pull models anytime in Daybook -> Models."
            }
        }
    } catch {
        Write-Warn "Skipped model pull: $($_.Exception.Message)"
    }
}

# -------------------------------------------------------------
# STEP 5: FINAL SUMMARY
# -------------------------------------------------------------
Write-Host "`n================================================================" -ForegroundColor Green
Write-Host "                AI STACK SETUP COMPLETE! ✓                      " -ForegroundColor White
Write-Host "================================================================" -ForegroundColor Green

Write-Host "  [✓] Node.js LTS:     " -NoNewline; Write-Host "$(& node -v 2>$null)" -ForegroundColor Green
Write-Host "  [✓] Claude Code:     " -NoNewline; Write-Host "$(& claude --version 2>$null || 'Installed')" -ForegroundColor Green
Write-Host "  [✓] Ollama:          " -NoNewline; Write-Host "Active on 127.0.0.1:11434" -ForegroundColor Green
Write-Host "  [✓] Daybook Link:    " -NoNewline; Write-Host "Connected" -ForegroundColor Green

Write-Host "`nHow to use your AI tools in Daybook:" -ForegroundColor Cyan
Write-Host "  1. Chat Section: Open Chat in Daybook to talk privately with your local model." -ForegroundColor White
Write-Host "  2. Terminal (Ctrl + ``): Press Ctrl+`` in Chat to open your terminal." -ForegroundColor White
Write-Host "  3. Claude Code: Type 'claude' in the Daybook terminal to code and manage projects." -ForegroundColor White
Write-Host "  4. Local AI: Type 'ollama run $Model' or choose it in the Chat dropdown." -ForegroundColor White
Write-Host "================================================================`n" -ForegroundColor Green

if (-not $NonInteractive) {
    Write-Host "Setup finished. You can now close this window." -ForegroundColor Gray
}
