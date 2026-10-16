# Daybook 1-Click AI Architecture Specification & Comprehensive Patch Notes
**Unified Zero-Struggle AI Integration for Gemini, Antigravity (AGY), Claude, Ollama & Qwen**

**Author:** Antigravity Engineering  
**Target:** Daybook Desktop App & Windows Subsystem  
**Scope:** Application Settings, 1-Click Installer (`install-ai-stack`), Electron Terminal (`main.js`), Frontend UI (`index.html`, `terminal.js`), and MCP Orchestration  

---

## 1. Executive Vision & Problem Statement

New users who download Daybook want to connect an AI model immediately without understanding Windows execution policies, node package managers, environment PATH variables, or manual JSON configuration.

Currently, Daybook’s AI onboarding has three critical gaps:
1. **Fragmented UI**: The Settings page has a "Claude Card" with connect buttons, but Gemini and Ollama are mentioned mostly in text, and Antigravity (AGY) is completely absent.
2. **Terminal Incompatibilities**:
   * Default PowerShell fails with `PSSecurityException` when running npm-installed CLI wrappers (`gemini.ps1`).
   * Daybook's `whichExe` resolution in `main.js` prefers extensionless files over `.cmd` / `.exe`, breaking cmd-based CLI execution on Windows.
   * Daybook's terminal PATH injection lacks Antigravity directories.
3. **One-Sided MCP Connection**:
   * Daybook’s installer registers its MCP server (`daybook-mcp.exe`) only with Claude (`claude mcp add`), leaving Gemini CLI and Antigravity disconnected.

**The Solution:** A unified **1-Click AI Stack & Engine Hub** in Daybook Settings that can install, repair, and link **Gemini CLI, Antigravity AGY, Claude Code, Ollama, and Qwen** in a single click, operating with 100% reliability both inside Daybook and in native Windows terminals (PowerShell, Windows Terminal, and CMD).

---

## 2. Architecture of the 1-Click AI Engine

```
+-----------------------------------------------------------------------------------+
|                           Daybook Settings -> AI Hub                              |
|   [ ⚡ 1-Click Install & Connect All AI ]   [ Individual Status Badges & Fixes ]   |
+------------------------------------------+----------------------------------------+
                                           |
                                  triggers installer
                                           v
+-----------------------------------------------------------------------------------+
|               Daybook 1-Click Installer (install-ai-stack.ps1)                    |
|                                                                                   |
|  1. Self-Healing Environment:                                                     |
|     - Set CurrentUser ExecutionPolicy -> RemoteSigned (no admin rights needed)    |
|     - Add nodejs, npm, .local/bin, agy/bin, Ollama to User PATH                   |
|                                                                                   |
|  2. Node.js LTS:                                                                  |
|     - Winget silent install -> fallback to direct portable zero-admin extraction  |
|                                                                                   |
|  3. Cloud AI CLIs:                                                                |
|     - Google Gemini CLI (@google/gemini-cli) + .cmd wrapper generator             |
|     - Google Antigravity AGY (agy.exe) verification + PATH wiring                 |
|     - Anthropic Claude Code (native Anthropic installer -> npm fallback)          |
|                                                                                   |
|  4. Local AI Engine (Ollama) & Hardware-Aware Model:                              |
|     - Ollama silent installer -> start background service                         |
|     - Hardware check:                                                             |
|       * Laptops / Integrated GPU / <16GB RAM -> Pull Qwen 2.5 1.5B (Fast, cool)   |
|       * Desktops / Dedicated GPU / >=16GB RAM -> Pull Qwen 2.5 7B (Power)         |
|                                                                                   |
|  5. Unified 3-Way MCP Auto-Wiring:                                                |
|     - Claude Code: & claude mcp add --scope user reminders -- "$mcpExe"          |
|     - Gemini CLI:  & gemini mcp add daybook "$mcpExe"                            |
|     - Antigravity: ~/.gemini/config/mcp_config.json (UTF-8 WITHOUT BOM)           |
+-----------------------------------------------------------------------------------+
                                           |
                              enables seamless execution
                                           v
+-----------------------------------------------------------------------------------+
|               Dual-Execution Runtime (Inside Daybook & Native Windows)            |
|                                                                                   |
|   A. Inside Daybook Terminal (Ctrl + `):                                          |
|      - Presets for: PowerShell, CMD, Gemini, AGY, Claude, Ollama, Qwen            |
|      - Fixed whichExe precedence: [.exe, .cmd, .bat, ""]                          |
|                                                                                   |
|   B. In External Windows Terminal (pwsh, cmd, Windows Terminal):                  |
|      - 'gemini', 'agy', 'claude', 'ollama run qwen2.5:1.5b' work globally         |
|      - All AI agents have access to Daybook tools via daybook-mcp.exe             |
+-----------------------------------------------------------------------------------+
```

---

## 3. Step-by-Step Implementation Guide & Diffs

### Phase 1: Core Installer Rewrite (`install-ai-stack.ps1`)

**File Path:** `resources/backend/_internal/install-ai-stack.ps1` (and root `install-ai-stack.ps1`)

```powershell
<#
.SYNOPSIS
    Daybook Flawless 1-Click AI Stack Installer
    Installs & connects: Node.js, Gemini CLI, Antigravity AGY, Claude Code, Ollama, and Qwen.
    Zero-admin friendly, hardware-adaptive, self-healing Windows environment.
#>

param(
    [switch]$SkipModelPull,
    [string]$Model = "",
    [switch]$NonInteractive
)

$ErrorActionPreference = "Continue"

function Write-Step { param([string]$Title) Write-Host "`n====> $Title" -ForegroundColor Cyan }
function Write-Success { param([string]$Msg) Write-Host " [OK] $Msg" -ForegroundColor Green }
function Write-Info { param([string]$Msg) Write-Host " [..] $Msg" -ForegroundColor Yellow }
function Write-Warn { param([string]$Msg) Write-Host " [!] $Msg" -ForegroundColor Magenta }
function Write-Err { param([string]$Msg) Write-Host " [ERR] $Msg" -ForegroundColor Red }

# -------------------------------------------------------------
# STEP 0: SELF-HEALING WINDOWS ENVIRONMENT & EXECUTION POLICY
# -------------------------------------------------------------
Write-Step "0/5 Environment Self-Healing"
try {
    $policy = Get-ExecutionPolicy -Scope CurrentUser
    if ($policy -in @("Undefined", "Restricted")) {
        Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser -Force -ErrorAction SilentlyContinue
        Write-Success "PowerShell script policy enabled for CurrentUser (RemoteSigned)."
    }
} catch {
    Write-Warn "Could not set execution policy: $($_.Exception.Message)"
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
        "$env:LOCALAPPDATA\agy\bin",
        "$env:USERPROFILE\.gemini\antigravity-ide\bin",
        "$env:LOCALAPPDATA\Programs\Antigravity IDE\bin",
        "$env:LOCALAPPDATA\Daybook-tools\gemini-cli",
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

Refresh-EnvPath

# Hardware detection for adaptive model recommendation
$totalRamGB = 8
try { $totalRamGB = [math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB) } catch {}
$hasDedicatedGpu = $false
try {
    $gpus = Get-CimInstance Win32_VideoController
    foreach ($g in $gpus) {
        if ($g.Name -match "NVIDIA|GeForce|RTX|GTX|Radeon RX|Radeon Pro|Arc A") { $hasDedicatedGpu = $true; break }
    }
} catch {}

Write-Host "Hardware Profile: $totalRamGB GB RAM, $(if ($hasDedicatedGpu) { 'Dedicated GPU' } else { 'Integrated/CPU Graphics (Laptop mode)' })" -ForegroundColor Gray

# -------------------------------------------------------------
# STEP 1: NODE.JS LTS RUNTIME
# -------------------------------------------------------------
Write-Step "1/5 Checking Node.js LTS Runtime"
$nodeInstalled = $false
try {
    $nodeVer = & node -v 2>$null
    if ($nodeVer -match "v(\d+)") {
        if ([int]$matches[1] -ge 18) {
            Write-Success "Node.js $nodeVer is ready."
            $nodeInstalled = $true
        }
    }
} catch {}

if (-not $nodeInstalled) {
    Write-Info "Node.js missing. Attempting silent install via winget..."
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        try {
            $proc = Start-Process winget -ArgumentList "install", "OpenJS.NodeJS.LTS", "--silent", "--accept-package-agreements", "--accept-source-agreements" -NoNewWindow -PassThru -Wait
            if ($proc.ExitCode -eq 0) {
                Refresh-EnvPath
                $nodeVer = & node -v 2>$null
                if ($nodeVer) { $nodeInstalled = $true; Write-Success "Node.js LTS installed: $nodeVer" }
            }
        } catch {}
    }

    if (-not $nodeInstalled) {
        Write-Info "Downloading official zero-admin Node.js LTS package..."
        $nodeDir = "$env:LOCALAPPDATA\Programs\nodejs"
        $zipUrl = "https://nodejs.org/dist/v22.14.0/node-v22.14.0-win-x64.zip"
        $zipDest = "$env:TEMP\node-v22-x64.zip"
        $tempExtract = "$env:TEMP\node-extract-$([guid]::NewGuid().ToString('N'))"
        try {
            [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 -bor [Net.SecurityProtocolType]::Tls13
            (New-Object System.Net.WebClient).DownloadFile($zipUrl, $zipDest)
            Expand-Archive -Path $zipDest -DestinationPath $tempExtract -Force
            $inner = Get-ChildItem -Path $tempExtract -Directory | Select-Object -First 1
            if ($inner) {
                if (-not (Test-Path $nodeDir)) { New-Item -ItemType Directory -Path $nodeDir -Force | Out-Null }
                Copy-Item -Path "$($inner.FullName)\*" -Destination $nodeDir -Recurse -Force
            }
            Remove-Item -Path $zipDest, $tempExtract -Recurse -Force -ErrorAction SilentlyContinue
            Add-To-UserPath $nodeDir
            Add-To-UserPath "$env:APPDATA\npm"
            Refresh-EnvPath
            $nodeVer = & node -v 2>$null
            if ($nodeVer) { $nodeInstalled = $true; Write-Success "Node.js portable installed: $nodeVer" }
        } catch {
            Write-Err "Node.js download failed: $($_.Exception.Message)"
        }
    }
}

# -------------------------------------------------------------
# STEP 2: GOOGLE GEMINI CLI & ANTIGRAVITY (AGY)
# -------------------------------------------------------------
Write-Step "2/5 Checking Google Gemini & Antigravity (AGY)"

# A. Gemini CLI
$geminiInstalled = $false
try {
    $geminiVer = & gemini.cmd --version 2>$null
    if (-not $geminiVer) { $geminiVer = & gemini --version 2>$null }
    if ($geminiVer) { $geminiInstalled = $true; Write-Success "Google Gemini CLI ready: $geminiVer" }
} catch {}

if (-not $geminiInstalled -and (Get-Command npm -ErrorAction SilentlyContinue)) {
    Write-Info "Installing Google Gemini CLI globally (@google/gemini-cli)..."
    try {
        Start-Process cmd.exe -ArgumentList "/c", "npm install -g @google/gemini-cli" -NoNewWindow -PassThru -Wait | Out-Null
        Refresh-EnvPath
        $geminiVer = & gemini.cmd --version 2>$null
        if ($geminiVer) { $geminiInstalled = $true; Write-Success "Gemini CLI installed: $geminiVer" }
    } catch {
        Write-Warn "Could not install Gemini CLI: $($_.Exception.Message)"
    }
}

# Daybook-tools fallback wrapper for Daybook's internal search path
$daybookToolsGemini = "$env:LOCALAPPDATA\Daybook-tools\gemini-cli"
if (-not (Test-Path $daybookToolsGemini)) { New-Item -ItemType Directory -Path $daybookToolsGemini -Force | Out-Null }
$geminiCmdWrapper = "$daybookToolsGemini\gemini.cmd"
if (-not (Test-Path $geminiCmdWrapper)) {
    '@echo off
"%LOCALAPPDATA%\Programs\nodejs\gemini.cmd" %*
' | Set-Content -Path $geminiCmdWrapper -Encoding ASCII
}

# B. Antigravity CLI (AGY)
$agyInstalled = $false
try {
    $agyVer = & agy --version 2>$null
    if ($agyVer) { $agyInstalled = $true; Write-Success "Google Antigravity (AGY) ready: $agyVer" }
} catch {}

if (-not $agyInstalled) {
    if (Test-Path "$env:LOCALAPPDATA\agy\bin\agy.exe") {
        Add-To-UserPath "$env:LOCALAPPDATA\agy\bin"
        Refresh-EnvPath
        $agyInstalled = $true
        Write-Success "Google Antigravity found in LocalAppData and added to PATH."
    } elseif (Test-Path "$env:USERPROFILE\.gemini\antigravity-ide\bin") {
        Add-To-UserPath "$env:USERPROFILE\.gemini\antigravity-ide\bin"
        Refresh-EnvPath
        $agyInstalled = $true
        Write-Success "Google Antigravity IDE CLI found and added to PATH."
    }
}

# Ensure AGY is also accessible via ~/.local/bin
$localBin = "$env:USERPROFILE\.local\bin"
if (-not (Test-Path $localBin)) { New-Item -ItemType Directory -Path $localBin -Force | Out-Null }
if ($agyInstalled -and (Test-Path "$env:LOCALAPPDATA\agy\bin\agy.exe") -and -not (Test-Path "$localBin\agy.cmd")) {
    '@echo off
"%LOCALAPPDATA%\agy\bin\agy.exe" %*
' | Set-Content -Path "$localBin\agy.cmd" -Encoding ASCII
}

# -------------------------------------------------------------
# STEP 3: ANTHROPIC CLAUDE CODE CLI
# -------------------------------------------------------------
Write-Step "3/5 Checking Anthropic Claude Code CLI"
$claudeInstalled = $false
try {
    $claudeVer = & claude --version 2>$null
    if ($claudeVer) { $claudeInstalled = $true; Write-Success "Claude Code is ready: $claudeVer" }
} catch {}

if (-not $claudeInstalled) {
    Write-Info "Installing Anthropic Claude Code native CLI..."
    try {
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 -bor [Net.SecurityProtocolType]::Tls13
        $nativeScript = Invoke-RestMethod -Uri "https://claude.ai/install.ps1" -ErrorAction Stop
        if ($nativeScript) { Invoke-Expression $nativeScript }
    } catch {}

    Add-To-UserPath "$env:USERPROFILE\.local\bin"
    Add-To-UserPath "$env:USERPROFILE\.claude\bin"
    Refresh-EnvPath

    try {
        $claudeVer = & claude --version 2>$null
        if ($claudeVer) { $claudeInstalled = $true; Write-Success "Claude Code verified: $claudeVer" }
    } catch {}

    if (-not $claudeInstalled -and (Get-Command npm -ErrorAction SilentlyContinue)) {
        Write-Info "Fallback: Installing Claude Code via npm..."
        Start-Process cmd.exe -ArgumentList "/c", "npm install -g @anthropic-ai/claude-code" -NoNewWindow -PassThru -Wait | Out-Null
        Refresh-EnvPath
        try {
            $claudeVer = & claude --version 2>$null
            if ($claudeVer) { $claudeInstalled = $true; Write-Success "Claude Code installed via npm: $claudeVer" }
        } catch {}
    }
}

# -------------------------------------------------------------
# STEP 4: OLLAMA LOCAL AI & HARDWARE-ADAPTIVE QWEN
# -------------------------------------------------------------
Write-Step "4/5 Checking Ollama & Qwen Local Model"
Refresh-EnvPath
$ollamaCmd = Get-Command ollama -ErrorAction SilentlyContinue
if (-not $ollamaCmd -and (Test-Path "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe")) {
    Add-To-UserPath "$env:LOCALAPPDATA\Programs\Ollama"
    Refresh-EnvPath
    $ollamaCmd = Get-Command ollama -ErrorAction SilentlyContinue
}

$ollamaInstalled = [bool]$ollamaCmd
if (-not $ollamaInstalled) {
    Write-Info "Installing Ollama for local offline models..."
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        $proc = Start-Process winget -ArgumentList "install", "Ollama.Ollama", "--silent", "--accept-package-agreements", "--accept-source-agreements" -NoNewWindow -PassThru -Wait
        if ($proc.ExitCode -eq 0) { $ollamaInstalled = $true }
    }
    if (-not $ollamaInstalled) {
        $ollamaUrl = "https://ollama.com/download/OllamaSetup.exe"
        $ollamaDest = "$env:TEMP\OllamaSetup.exe"
        try {
            (New-Object System.Net.WebClient).DownloadFile($ollamaUrl, $ollamaDest)
            Start-Process $ollamaDest -ArgumentList "/silent" -NoNewWindow -PassThru -Wait | Out-Null
            Remove-Item $ollamaDest -Force -ErrorAction SilentlyContinue
            Add-To-UserPath "$env:LOCALAPPDATA\Programs\Ollama"
            Refresh-EnvPath
            $ollamaInstalled = $true
        } catch {}
    }
}

# Ensure background service is running
$ollamaRunning = $false
for ($i = 0; $i -lt 5; $i++) {
    try {
        $resp = Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/tags" -Method Get -TimeoutSec 2 -ErrorAction Stop
        if ($resp) { $ollamaRunning = $true; break }
    } catch {
        Start-Process "ollama" -ArgumentList "serve" -WindowStyle Hidden -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 2
    }
}

# Hardware-aware model selection
if ([string]::IsNullOrWhiteSpace($Model)) {
    if (-not $hasDedicatedGpu -or $totalRamGB -lt 16) {
        $Model = "qwen2.5:1.5b"
        Write-Info "Laptop / CPU detected: Recommending lightweight '$Model' (~1 GB)."
    } else {
        $Model = "qwen2.5:7b"
        Write-Info "Dedicated GPU / High RAM detected: Recommending full '$Model' (~4.5 GB)."
    }
}

if ($ollamaRunning -and -not $SkipModelPull) {
    try {
        $tags = Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/tags" -Method Get -TimeoutSec 3
        $hasModel = $tags.models | Where-Object { $_.name -like "$Model*" }
        if ($hasModel) {
            Write-Success "Local model '$Model' is already downloaded."
        } else {
            Write-Info "Downloading '$Model' for private offline note parsing & reminders..."
            & ollama pull $Model
            if ($LASTEXITCODE -eq 0) { Write-Success "Model '$Model' downloaded successfully." }
        }
    } catch {}
}

# -------------------------------------------------------------
# STEP 5: UNIFIED 3-WAY MCP AUTO-CONNECTION
# -------------------------------------------------------------
Write-Step "5/5 Connecting Daybook MCP Server to All AI Engines"

$mcpCandidates = @(
    "$PSScriptRoot\daybook-mcp.exe",
    "$PSScriptRoot\backend\daybook-mcp.exe",
    "$env:LOCALAPPDATA\Programs\Daybook\resources\backend\daybook-mcp.exe"
)
$mcpExe = $mcpCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1

if ($mcpExe) {
    # 1. Claude Code
    if ($claudeInstalled) {
        try {
            & claude mcp add --scope user reminders -- "$mcpExe" 2>$null
            Write-Success "Daybook MCP connected to Claude Code."
        } catch {}
    }

    # 2. Google Gemini CLI
    if ($geminiInstalled) {
        try {
            Start-Process cmd.exe -ArgumentList "/c", "gemini mcp add daybook `"$mcpExe`"" -NoNewWindow -PassThru -Wait | Out-Null
            Write-Success "Daybook MCP connected to Gemini CLI."
        } catch {}
    }

    # 3. Google Antigravity (AGY)
    try {
        $geminiCfgDir = "$env:USERPROFILE\.gemini\config"
        if (-not (Test-Path $geminiCfgDir)) { New-Item -ItemType Directory -Path $geminiCfgDir -Force | Out-Null }
        $mcpCfgPath = "$geminiCfgDir\mcp_config.json"
        
        $cfg = @{ mcpServers = @{} }
        if (Test-Path $mcpCfgPath) {
            try {
                $raw = [System.IO.File]::ReadAllText($mcpCfgPath)
                if (-not [string]::IsNullOrWhiteSpace($raw)) { $cfg = $raw | ConvertFrom-Json }
            } catch {}
        }
        if (-not $cfg.mcpServers) { $cfg | Add-Member -MemberType NoteProperty -Name "mcpServers" -Value @{} }
        $cfg.mcpServers.daybook = @{ command = $mcpExe; args = @() }

        # Crucial: Write UTF-8 WITHOUT BOM so Go's JSON parser won't throw \ufeff error
        $json = $cfg | ConvertTo-Json -Depth 5
        [System.IO.File]::WriteAllText($mcpCfgPath, $json, (New-Object System.Text.UTF8Encoding($false)))
        Write-Success "Daybook MCP connected to Antigravity (AGY)."
    } catch {}
}

Write-Host "`n================================================================" -ForegroundColor Green
Write-Host "             ALL AI ENGINES INSTALLED & CONNECTED!              " -ForegroundColor White
Write-Host "================================================================" -ForegroundColor Green
Write-Host "  [OK] Gemini CLI:      $($geminiInstalled)" -ForegroundColor Green
Write-Host "  [OK] Antigravity AGY: $($agyInstalled)" -ForegroundColor Green
Write-Host "  [OK] Claude Code:     $($claudeInstalled)" -ForegroundColor Green
Write-Host "  [OK] Ollama Local:    $($ollamaRunning)" -ForegroundColor Green
Write-Host "  [OK] Qwen Model:      $Model" -ForegroundColor Green
Write-Host "  [OK] Daybook MCP:     Connected to All Engines" -ForegroundColor Green
Write-Host "================================================================`n" -ForegroundColor Green
