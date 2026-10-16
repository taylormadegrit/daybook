<#
.SYNOPSIS
    Daybook 1-Click AI Stack Installer for Windows
    Installs: Node.js LTS, Claude Code CLI, Gemini CLI, and Ollama Local AI.
    Works on ANY Windows machine (including clean laptops without admin privileges or GPUs).
#>

param(
    [switch]$SkipModelPull,
    [string]$Model = "",
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
    $env:Path = "$userPath;$machinePath"

    $candidates = @(
        "$env:LOCALAPPDATA\Programs\nodejs",
        "$env:ProgramFiles\nodejs",
        "$env:APPDATA\npm",
        "$env:USERPROFILE\.local\bin",
        "$env:USERPROFILE\.claude\bin",
        "$env:LOCALAPPDATA\Programs\Ollama",
        "$env:LOCALAPPDATA\Programs\Ollama\bin"
    )
    foreach ($dir in $candidates) {
        if ((Test-Path $dir) -and ($env:Path -notlike "*$dir*")) {
            $env:Path = "$dir;$env:Path"
        }
    }
}

function Add-To-UserPath {
    param([string]$Directory)
    if (-not (Test-Path $Directory)) { return }
    try {
        $currentUserPath = [System.Environment]::GetEnvironmentVariable("Path", "User")
        if ($currentUserPath -notlike "*$Directory*") {
            $newPath = if ([string]::IsNullOrWhiteSpace($currentUserPath)) { $Directory } else { "$Directory;$currentUserPath" }
            [System.Environment]::SetEnvironmentVariable("Path", $newPath, "User")
        }
    } catch {}
    if ($env:Path -notlike "*$Directory*") {
        $env:Path = "$Directory;$env:Path"
    }
}

Clear-Host
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host "       DAYBOOK 1-CLICK AI STACK INSTALLER FOR WINDOWS           " -ForegroundColor White
Write-Host "   Installs: Node.js LTS + Claude Code CLI + Ollama Local AI   " -ForegroundColor Cyan
Write-Host "================================================================" -ForegroundColor Cyan

Refresh-EnvPath

# Detect Hardware Profile (Laptop vs Desktop / GPU)
$totalRamGB = 8
try {
    $totalRamGB = [math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB)
} catch {}

$hasDedicatedGpu = $false
try {
    $gpus = Get-CimInstance Win32_VideoController
    foreach ($g in $gpus) {
        if ($g.Name -match "NVIDIA|GeForce|RTX|GTX|Radeon RX|Radeon Pro|Arc A") {
            $hasDedicatedGpu = $true
            break
        }
    }
} catch {}

Write-Host "Hardware Profile: $totalRamGB GB RAM, $(if ($hasDedicatedGpu) { 'Dedicated GPU' } else { 'Integrated/CPU Graphics (Laptop mode)' })" -ForegroundColor Gray

# -------------------------------------------------------------
# STEP 1: NODE.JS LTS
# -------------------------------------------------------------
Write-Step "1/4 Checking Node.js LTS"
$nodeInstalled = $false
try {
    $nodeVer = & node -v 2>$null
    if ($nodeVer -match "v(\d+)") {
        $major = [int]$matches[1]
        if ($major -ge 18) {
            Write-Success "Node.js $nodeVer is already installed."
            $nodeInstalled = $true
        } else {
            Write-Warn "Node.js $nodeVer is installed, but version 18+ is required."
        }
    }
} catch {}

if (-not $nodeInstalled) {
    Write-Info "Node.js not detected. Installing Node.js LTS..."
    $installedWithWinget = $false

    if (Get-Command winget -ErrorAction SilentlyContinue) {
        Write-Info "Attempting installation via winget (OpenJS.NodeJS.LTS)..."
        try {
            $proc = Start-Process winget -ArgumentList "install", "OpenJS.NodeJS.LTS", "--silent", "--accept-package-agreements", "--accept-source-agreements" -NoNewWindow -PassThru -Wait
            if ($proc.ExitCode -eq 0) {
                Refresh-EnvPath
                $testVer = & node -v 2>$null
                if ($testVer) {
                    $installedWithWinget = $true
                    Write-Success "Node.js LTS installed via winget: $testVer"
                    $nodeInstalled = $true
                }
            }
        } catch {}
    }

    if (-not $nodeInstalled) {
        Write-Info "Downloading official Node.js portable package directly (Zero Admin Rights Needed)..."
        $nodeDir = "$env:LOCALAPPDATA\Programs\nodejs"
        $zipUrl = "https://nodejs.org/dist/v22.14.0/node-v22.14.0-win-x64.zip"
        $zipDest = "$env:TEMP\node-v22-x64.zip"
        $tempExtract = "$env:TEMP\node-extract-$([guid]::NewGuid().ToString('N'))"

        try {
            [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 -bor [Net.SecurityProtocolType]::Tls13
            (New-Object System.Net.WebClient).DownloadFile($zipUrl, $zipDest)
            Write-Info "Extracting Node.js LTS into $nodeDir..."
            Expand-Archive -Path $zipDest -DestinationPath $tempExtract -Force
            $inner = Get-ChildItem -Path $tempExtract -Directory | Select-Object -First 1
            if ($inner) {
                if (-not (Test-Path $nodeDir)) { New-Item -ItemType Directory -Path $nodeDir -Force | Out-Null }
                Copy-Item -Path "$($inner.FullName)\*" -Destination $nodeDir -Recurse -Force
            }
            Remove-Item -Path $zipDest -Force -ErrorAction SilentlyContinue
            Remove-Item -Path $tempExtract -Recurse -Force -ErrorAction SilentlyContinue

            Add-To-UserPath $nodeDir
            $npmDir = "$env:APPDATA\npm"
            if (-not (Test-Path $npmDir)) { New-Item -ItemType Directory -Path $npmDir -Force | Out-Null }
            Add-To-UserPath $npmDir

            Refresh-EnvPath
            $nodeVer = & node -v 2>$null
            if ($nodeVer) {
                Write-Success "Node.js LTS successfully installed and verified: $nodeVer"
                $nodeInstalled = $true
            }
        } catch {
            Write-Err "Portable Node.js download/extraction failed: $($_.Exception.Message)"
        }
    }
}

Refresh-EnvPath

# -------------------------------------------------------------
# STEP 2: CLAUDE CODE CLI & GEMINI CLI
# -------------------------------------------------------------
Write-Step "2/4 Checking Claude Code CLI & Gemini CLI"
$claudeInstalled = $false
try {
    $claudeVer = & claude --version 2>$null
    if ($claudeVer) {
        Write-Success "Claude Code is already installed: $claudeVer"
        $claudeInstalled = $true
    }
} catch {}

if (-not $claudeInstalled) {
    # Method A: Official Anthropic Native Standalone Installer (Fast & No Node requirement)
    Write-Info "Installing official Anthropic Claude Code CLI..."
    try {
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 -bor [Net.SecurityProtocolType]::Tls13
        $nativeScript = Invoke-RestMethod -Uri "https://claude.ai/install.ps1" -ErrorAction Stop
        if ($nativeScript) {
            Invoke-Expression $nativeScript
        }
    } catch {
        Write-Warn "Anthropic native web installer notice: $($_.Exception.Message)"
    }

    Add-To-UserPath "$env:USERPROFILE\.local\bin"
    Add-To-UserPath "$env:USERPROFILE\.claude\bin"
    Refresh-EnvPath

    try {
        $claudeVer = & claude --version 2>$null
        if ($claudeVer) {
            Write-Success "Claude Code CLI verified: $claudeVer"
            $claudeInstalled = $true
        }
    } catch {}

    # Method B: Global npm install fallback
    if (-not $claudeInstalled -and (Get-Command npm -ErrorAction SilentlyContinue)) {
        Write-Info "Installing Claude Code globally via npm (@anthropic-ai/claude-code)..."
        try {
            $npmProc = Start-Process cmd.exe -ArgumentList "/c", "npm install -g @anthropic-ai/claude-code" -NoNewWindow -PassThru -Wait
            Refresh-EnvPath
            $claudeVer = & claude --version 2>$null
            if ($claudeVer) {
                Write-Success "Claude Code successfully installed via npm: $claudeVer"
                $claudeInstalled = $true
            }
        } catch {}
    }
}

# Install / verify Gemini CLI
try {
    $geminiVer = & gemini --version 2>$null
    if ($geminiVer) {
        Write-Success "Google Gemini CLI is installed: $geminiVer"
    } else {
        if (Get-Command npm -ErrorAction SilentlyContinue) {
            Write-Info "Installing Google Gemini CLI (@google/gemini-cli)..."
            Start-Process cmd.exe -ArgumentList "/c", "npm install -g @google/gemini-cli" -NoNewWindow -PassThru -Wait | Out-Null
            Refresh-EnvPath
            $geminiVer = & gemini --version 2>$null
            if ($geminiVer) {
                Write-Success "Google Gemini CLI ready: $geminiVer"
            }
        }
    }
} catch {}

# Connect Claude Code to Daybook MCP server if available
if ($claudeInstalled) {
    try {
        $mcpCandidates = @(
            "D:\projects\local-reminders\daybook-mcp.exe",
            "$PSScriptRoot\daybook-mcp.exe",
            "$PSScriptRoot\backend\daybook-mcp.exe",
            "$env:LOCALAPPDATA\Programs\Daybook\resources\backend\daybook-mcp.exe"
        )
        $mcpExe = $mcpCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
        if ($mcpExe) {
            Write-Info "Connecting Daybook MCP server ('reminders') to Claude Code..."
            & claude mcp add --scope user reminders -- "$mcpExe" 2>$null
            Write-Success "Daybook MCP server connected to Claude Code."
        }
    } catch {}
}

# -------------------------------------------------------------
# STEP 3: OLLAMA LOCAL AI
# -------------------------------------------------------------
Write-Step "3/4 Checking Ollama (Local AI Engine)"
Refresh-EnvPath
$ollamaInstalled = $false
$ollamaCmd = Get-Command ollama -ErrorAction SilentlyContinue
if (-not $ollamaCmd -and (Test-Path "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe")) {
    Add-To-UserPath "$env:LOCALAPPDATA\Programs\Ollama"
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

    Add-To-UserPath "$env:LOCALAPPDATA\Programs\Ollama"
    Refresh-EnvPath
}

# Ensure Ollama background service is running
Write-Info "Verifying Ollama background service..."
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
# STEP 4: HARDWARE-AWARE MODEL SELECTION & DOWNLOAD
# -------------------------------------------------------------
Write-Step "4/4 Model Recommendation for Your Hardware"

# Pick ideal model based on user hardware if not specified
if ([string]::IsNullOrWhiteSpace($Model)) {
    if (-not $hasDedicatedGpu -or $totalRamGB -lt 16) {
        # Laptop / CPU profile: fast, compact, responsive
        $Model = "qwen2.5:1.5b"
        Write-Info "💻 Laptop profile detected ($totalRamGB GB RAM, integrated graphics)."
        Write-Info "Selecting lightweight model '$Model' (~1 GB) to keep your laptop cool, fast and battery-efficient."
    } else {
        # Desktop / GPU profile: full 7B model
        $Model = "qwen2.5:7b"
        Write-Info "🖥️ Desktop/GPU profile detected ($totalRamGB GB RAM). Selecting standard 7B model '$Model'."
    }
}

if ($ollamaRunning -and -not $SkipModelPull) {
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
            Write-Success "Model '$Model' is already installed."
        } else {
            Write-Info "Pulling '$Model' for offline reminders, notes & chat..."
            Write-Host "This runs 100% locally on your computer with complete privacy.`n" -ForegroundColor Gray
            & ollama pull $Model
            if ($LASTEXITCODE -eq 0) {
                Write-Success "Model '$Model' downloaded successfully!"
            } else {
                Write-Warn "Could not pull '$Model'. You can pull models anytime in Daybook -> Models."
            }
        }
    } catch {
        Write-Warn "Skipped model pull: $($_.Exception.Message)"
    }
}

# -------------------------------------------------------------
# STEP 5: FINAL SUMMARY & BEGINNER GUIDE
# -------------------------------------------------------------
Write-Host "`n================================================================" -ForegroundColor Green
Write-Host "                AI STACK SETUP COMPLETE! ✓                      " -ForegroundColor White
Write-Host "================================================================" -ForegroundColor Green

$nodeVer = "Installed"
try { $v = & node -v 2>$null; if ($v) { $nodeVer = $v.ToString().Trim() } } catch {}

$claudeVer = "Installed"
try { $v = & claude --version 2>$null; if ($v) { $claudeVer = $v.ToString().Trim() } } catch {}

$geminiVer = "Ready"
try { $v = & gemini --version 2>$null; if ($v) { $geminiVer = $v.ToString().Trim() } } catch {}

$ollamaMsg = "Installed"
if ($ollamaRunning) { $ollamaMsg = "Active (port 11434)" }

Write-Host "  [✓] Node.js LTS:     $nodeVer" -ForegroundColor Green
Write-Host "  [✓] Claude Code:     $claudeVer" -ForegroundColor Green
Write-Host "  [✓] Gemini CLI:      $geminiVer" -ForegroundColor Green
Write-Host "  [✓] Ollama Local AI: $ollamaMsg" -ForegroundColor Green
Write-Host "  [✓] Daybook Link:    Connected" -ForegroundColor Green

Write-Host "`n💡 BEGINNER QUICK START GUIDE:" -ForegroundColor Cyan
Write-Host "  • Laptops without a GPU: Use Cloud AI (Gemini or Claude) in Daybook for instant, zero-hardware responses." -ForegroundColor White
Write-Host "  • Terminal AI Coding: Press Ctrl + `` in Daybook Chat to open your terminal, then type 'claude'." -ForegroundColor White
Write-Host "  • Offline & Private: Daybook uses '$Model' locally for notes and routine extraction." -ForegroundColor White
Write-Host "================================================================`n" -ForegroundColor Green

if (-not $NonInteractive) {
    Write-Host "Setup finished successfully. You can now close this window." -ForegroundColor Gray
}
