<#
.SYNOPSIS
    Daybook 1-Click AI Stack Installer for Windows
    Installs: Node.js LTS, Claude Code CLI, Gemini CLI, and Ollama Local AI.
    Works on ANY Windows machine (including clean laptops without admin privileges or GPUs).
#>

param(
    [switch]$SkipModelPull,
    [string]$Model = "",
    [switch]$NonInteractive,
    [ValidateSet("all", "gemini", "claude", "agy", "ollama")]
    [string]$Only = "all",
    [string]$McpExe = "",
    [string]$ToolsDir = "$env:LOCALAPPDATA\Daybook-tools",
    [string]$GeminiVersion = "0.62.0"
)

$ErrorActionPreference = "Continue"
$results = [ordered]@{}

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

function Show-Result($label, $ok, $detail) {
    if ($ok) { Write-Host ("  [OK]   {0,-18} {1}" -f $label, $detail) -ForegroundColor Green }
    else     { Write-Host ("  [FAIL] {0,-18} {1}" -f $label, $detail) -ForegroundColor Red }
}

function Refresh-EnvPath {
    $machinePath = [System.Environment]::GetEnvironmentVariable("Path", "Machine")
    $userPath = [System.Environment]::GetEnvironmentVariable("Path", "User")
    $env:Path = "$userPath;$machinePath"

    $candidates = @(
        (Join-Path $ToolsDir "nodejs"),
        (Join-Path $ToolsDir "gemini-cli"),
        "$env:LOCALAPPDATA\agy\bin",
        "$env:LOCALAPPDATA\Microsoft\WinGet\Links",
        "$env:USERPROFILE\.gemini\antigravity-ide\bin",
        "$env:LOCALAPPDATA\Programs\Antigravity IDE\bin",
        "$env:LOCALAPPDATA\Programs\nodejs",
        "$env:ProgramFiles\nodejs",
        "$env:APPDATA\npm",
        "$env:USERPROFILE\.local\bin",
        "$env:USERPROFILE\.claude\bin",
        "$env:LOCALAPPDATA\Programs\Ollama",
        "$env:LOCALAPPDATA\Programs\Ollama\bin"
    )
    foreach ($dir in $candidates) {
        if ($dir -and (Test-Path $dir) -and ($env:Path -notlike "*$dir*")) {
            $env:Path = "$dir;$env:Path"
        }
    }
}

function Add-To-UserPath {
    param([string]$Directory, [switch]$Prepend)
    if (-not (Test-Path $Directory)) { return }
    try {
        $currentUserPath = [System.Environment]::GetEnvironmentVariable("Path", "User")
        if ($currentUserPath -notlike "*$Directory*") {
            $newPath = if ([string]::IsNullOrWhiteSpace($currentUserPath)) {
                $Directory
            } elseif ($Prepend) {
                "$Directory;$currentUserPath"
            } else {
                "$Directory;$currentUserPath"
            }
            [System.Environment]::SetEnvironmentVariable("Path", $newPath, "User")
        }
    } catch {}
    if ($env:Path -notlike "*$Directory*") {
        $env:Path = "$Directory;$env:Path"
    }
}

function Resolve-McpExe {
    if ($McpExe -and (Test-Path $McpExe)) { return $McpExe }
    $candidates = @(
        "$PSScriptRoot\daybook-mcp.exe",
        "$PSScriptRoot\backend\daybook-mcp.exe",
        "$env:LOCALAPPDATA\Programs\Daybook\resources\backend\daybook-mcp.exe"
    )
    return ($candidates | Where-Object { Test-Path $_ } | Select-Object -First 1)
}

function Register-GeminiMcp {
    param([string]$ExePath)
    if (-not $ExePath -or -not (Test-Path $ExePath)) {
        Write-Err "Daybook MCP connector executable not found ($ExePath)."
        return $false
    }
    $dir  = Join-Path $env:USERPROFILE ".gemini"
    $file = Join-Path $dir "settings.json"
    New-Item -ItemType Directory -Force $dir | Out-Null
    $cfg = [pscustomobject]@{}
    if (Test-Path $file) {
        $raw = Get-Content $file -Raw
        if ($raw -and $raw.Trim()) {
            try {
                $cfg = $raw | ConvertFrom-Json
            } catch {
                Write-Err "settings.json isn't plain JSON, so Daybook left it alone. Add the 'daybook' entry by hand."
                return $false
            }
        }
        Copy-Item $file "$file.daybook-backup" -Force
    }
    if (-not $cfg.mcpServers) {
        $cfg | Add-Member -NotePropertyName mcpServers -NotePropertyValue ([pscustomobject]@{}) -Force
    }
    $entry = [pscustomobject]@{
        command = $ExePath
        args    = @("mcp")
        timeout = 90000
    }
    $cfg.mcpServers | Add-Member -NotePropertyName daybook -NotePropertyValue $entry -Force
    $json = $cfg | ConvertTo-Json -Depth 20
    # Ensure single-element args array stays a JSON array even on PowerShell 5.1 edge cases
    $json = [regex]::Replace($json, '"args"\s*:\s*"mcp"', '"args": ["mcp"]')
    # Windows PowerShell 5.1 adds a BOM with -Encoding utf8, so write UTF-8 without one
    [IO.File]::WriteAllText($file, $json, (New-Object Text.UTF8Encoding $false))
    return $true
}

function Find-AgyExe {
    $fromPath = Get-Command agy -ErrorAction SilentlyContinue
    if ($fromPath -and $fromPath.Source -and (Test-Path $fromPath.Source)) {
        return $fromPath.Source
    }
    $candidates = @(
        "$env:LOCALAPPDATA\agy\bin\agy.exe",
        "$env:LOCALAPPDATA\Microsoft\WinGet\Links\agy.exe",
        "$env:USERPROFILE\.gemini\antigravity-ide\bin\agy.exe",
        "$env:LOCALAPPDATA\Programs\Antigravity IDE\bin\agy.exe"
    )
    return ($candidates | Where-Object { Test-Path $_ } | Select-Object -First 1)
}

function Merge-AgyMcpFile {
    param([string]$FilePath, [string]$ExePath)
    $dir = Split-Path -Parent $FilePath
    New-Item -ItemType Directory -Force $dir | Out-Null
    $cfg = [pscustomobject]@{}
    if (Test-Path $FilePath) {
        $raw = Get-Content $FilePath -Raw
        if ($raw -and $raw.Trim()) {
            try {
                $cfg = $raw | ConvertFrom-Json
            } catch {
                Write-Err "$(Split-Path -Leaf $FilePath) isn't plain JSON, so Daybook left it alone. Add the 'daybook' entry by hand."
                return $false
            }
        }
        Copy-Item $FilePath "$FilePath.daybook-backup" -Force
    }
    if (-not $cfg.mcpServers) {
        $cfg | Add-Member -NotePropertyName mcpServers -NotePropertyValue ([pscustomobject]@{}) -Force
    }
    $entry = [pscustomobject]@{
        command = $ExePath
        args    = @("mcp")
    }
    $cfg.mcpServers | Add-Member -NotePropertyName daybook -NotePropertyValue $entry -Force
    $json = $cfg | ConvertTo-Json -Depth 20
    $json = [regex]::Replace($json, '"args"\s*:\s*"mcp"', '"args": ["mcp"]')
    [IO.File]::WriteAllText($FilePath, $json, (New-Object Text.UTF8Encoding $false))
    return $true
}

function Register-AgyMcp {
    param([string]$ExePath, [string]$AgyExe = "")
    if (-not $ExePath -or -not (Test-Path $ExePath)) {
        Write-Err "Daybook MCP connector executable not found ($ExePath)."
        return $false
    }
    $cliOk = $false
    if ($AgyExe -and (Test-Path $AgyExe)) {
        try {
            & $AgyExe mcp add daybook "$ExePath" mcp 2>$null | Out-Null
            if ($LASTEXITCODE -eq 0) { $cliOk = $true }
        } catch {}
    }
    $files = @(
        (Join-Path $env:USERPROFILE ".gemini\config\mcp_config.json"),
        (Join-Path $env:USERPROFILE ".gemini\antigravity\mcp_config.json")
    )
    $allFilesOk = $true
    foreach ($f in $files) {
        if (-not (Merge-AgyMcpFile -FilePath $f -ExePath $ExePath)) {
            $allFilesOk = $false
        }
    }
    return ($cliOk -or $allFilesOk)
}

function Test-McpHandshake {
    param([string]$ExePath, [int]$TimeoutMs = 90000)
    if (-not $ExePath -or -not (Test-Path $ExePath)) { return $false }
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $ExePath
    $psi.Arguments = "mcp"
    $psi.UseShellExecute = $false
    $psi.RedirectStandardInput = $true
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.CreateNoWindow = $true
    $proc = New-Object System.Diagnostics.Process
    $proc.StartInfo = $psi
    # Windows PowerShell's redirected stdin uses [Console]::InputEncoding, which writes a UTF-8 BOM as soon as
    # the pipe opens; the connector then can't parse the first message and never answers. Send plain UTF-8.
    $prevInputEncoding = [Console]::InputEncoding
    try {
        try { [Console]::InputEncoding = New-Object System.Text.UTF8Encoding $false } catch {}
        $started = $proc.Start()
        try { [Console]::InputEncoding = $prevInputEncoding } catch {}
        if (-not $started) { return $false }
        $req = '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"daybook-installer","version":"1.8.1"}}}'
        $proc.StandardInput.WriteLine($req)
        $proc.StandardInput.Flush()
        $readTask = $proc.StandardOutput.ReadLineAsync()
        if ($readTask.Wait($TimeoutMs)) {
            $line = $readTask.Result
            if ($line -and $line -match '"jsonrpc"\s*:\s*"2\.0"') {
                return $true
            }
        }
        return $false
    } catch {
        return $false
    } finally {
        try { [Console]::InputEncoding = $prevInputEncoding } catch {}
        try { if (-not $proc.HasExited) { $proc.Kill() } } catch {}
        try { $proc.Dispose() } catch {}
    }
}

function Install-PortableNode {
    param([string]$TargetNodeDir)
    $arch = if ($env:PROCESSOR_ARCHITECTURE -eq "ARM64") { "arm64" } else { "x64" }
    $ver = "v22.14.0"
    $zipName = "node-$ver-win-$arch.zip"
    $baseUrl = "https://nodejs.org/dist/$ver"
    $zipUrl = "$baseUrl/$zipName"
    $shaUrl = "$baseUrl/SHASUMS256.txt"
    $zipDest = Join-Path $env:TEMP $zipName
    $tempExtract = Join-Path $env:TEMP "node-extract-$([guid]::NewGuid().ToString('N'))"

    try {
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 -bor [Net.SecurityProtocolType]::Tls13
        $wc = New-Object System.Net.WebClient
        Write-Info "Downloading official Node.js portable package ($zipName, Zero Admin Rights Needed)..."
        $wc.DownloadFile($zipUrl, $zipDest)

        Write-Info "Verifying SHA-256 checksum from $shaUrl..."
        $shasums = $wc.DownloadString($shaUrl)
        $expectedHash = $null
        foreach ($line in ($shasums -split "`r?`n")) {
            if ($line -match "^([0-9a-fA-F]{64})\s+\*?$([regex]::Escape($zipName))$") {
                $expectedHash = $matches[1].ToLowerInvariant()
                break
            }
        }
        if (-not $expectedHash) {
            Write-Err "Could not find checksum for $zipName in SHASUMS256.txt."
            return $false
        }
        $actualHash = (Get-FileHash -Path $zipDest -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($actualHash -ne $expectedHash) {
            Write-Err "SHA-256 mismatch for $zipName (expected $expectedHash, got $actualHash)."
            Remove-Item -Path $zipDest -Force -ErrorAction SilentlyContinue
            return $false
        }
        Write-Success "SHA-256 checksum verified."

        Write-Info "Extracting Node.js LTS into $TargetNodeDir..."
        Expand-Archive -Path $zipDest -DestinationPath $tempExtract -Force
        $inner = Get-ChildItem -Path $tempExtract -Directory | Select-Object -First 1
        if ($inner) {
            if (-not (Test-Path $TargetNodeDir)) { New-Item -ItemType Directory -Path $TargetNodeDir -Force | Out-Null }
            Copy-Item -Path "$($inner.FullName)\*" -Destination $TargetNodeDir -Recurse -Force
        }
        Remove-Item -Path $zipDest -Force -ErrorAction SilentlyContinue
        Remove-Item -Path $tempExtract -Recurse -Force -ErrorAction SilentlyContinue

        Add-To-UserPath $TargetNodeDir -Prepend
        $npmDir = "$env:APPDATA\npm"
        if (-not (Test-Path $npmDir)) { New-Item -ItemType Directory -Path $npmDir -Force | Out-Null }
        Add-To-UserPath $npmDir

        $env:Path = "$TargetNodeDir;$env:Path"
        $nodeVer = & "$TargetNodeDir\node.exe" -v 2>$null
        if ($nodeVer) {
            Write-Success "Node.js LTS successfully installed and verified: $nodeVer"
            return $true
        }
    } catch {
        Write-Err "Portable Node.js download/extraction failed: $($_.Exception.Message)"
    }
    return $false
}

Clear-Host
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host "       DAYBOOK 1-CLICK AI STACK INSTALLER FOR WINDOWS           " -ForegroundColor White
Write-Host "   Mode: $($Only.ToUpper()) | Tools folder: $ToolsDir           " -ForegroundColor Cyan
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

$runNode   = $Only -in @("all", "gemini")
$runClaude = $Only -in @("all", "claude")
$runGemini = $Only -in @("all", "gemini")
$runAgy    = $Only -in @("all", "agy")
$runOllama = $Only -in @("all", "ollama")

$nodeInstalled = $false
$nodeDetail = "Not installed"

# -------------------------------------------------------------
# STEP 1: NODE.JS LTS (20+)
# -------------------------------------------------------------
if ($runNode) {
    Write-Step "Checking Node.js (20 or newer)"
    $hadOldNode = $false
    try {
        $nodeVer = & node -v 2>$null
        if ($nodeVer -match "v(\d+)") {
            $major = [int]$matches[1]
            if ($major -ge 20) {
                Write-Success "Node.js $nodeVer is already installed."
                $nodeInstalled = $true
                $nodeDetail = $nodeVer.ToString().Trim()
            } else {
                Write-Warn "Node.js $nodeVer is too old (Gemini CLI needs 20 or newer). Installing a private copy for Daybook..."
                $hadOldNode = $true
            }
        }
    } catch {}

    if (-not $nodeInstalled) {
        # If the user already has an older Node, do not replace it via winget; install Daybook's private portable copy
        if (-not $hadOldNode -and (Get-Command winget -ErrorAction SilentlyContinue)) {
            Write-Info "Attempting installation via winget (OpenJS.NodeJS.LTS)..."
            try {
                $proc = Start-Process winget -ArgumentList "install", "OpenJS.NodeJS.LTS", "--silent", "--accept-package-agreements", "--accept-source-agreements" -NoNewWindow -PassThru -Wait
                if ($proc.ExitCode -eq 0) {
                    Refresh-EnvPath
                    $testVer = & node -v 2>$null
                    if ($testVer -match "v(\d+)" -and ([int]$matches[1] -ge 20)) {
                        Write-Success "Node.js LTS installed via winget: $testVer"
                        $nodeInstalled = $true
                        $nodeDetail = $testVer.ToString().Trim()
                    }
                }
            } catch {}
        }

        if (-not $nodeInstalled) {
            $portableDir = if ($hadOldNode) { Join-Path $ToolsDir "nodejs" } else { "$env:LOCALAPPDATA\Programs\nodejs" }
            if (Install-PortableNode -TargetNodeDir $portableDir) {
                $nodeInstalled = $true
                $v = & node -v 2>$null
                $nodeDetail = if ($v) { $v.ToString().Trim() } else { "v22.14.0" }
            }
        }
    }
    $results["Node.js (20+)"] = @{ ok = $nodeInstalled; detail = $nodeDetail }
}

Refresh-EnvPath
$resolvedMcpExe = Resolve-McpExe

# -------------------------------------------------------------
# STEP 2A: CLAUDE CODE CLI + MCP CONNECTION
# -------------------------------------------------------------
if ($runClaude) {
    Write-Step "Checking Claude Code CLI"
    $claudeInstalled = $false
    $claudeDetail = "Not installed"
    try {
        $claudeVer = & claude --version 2>$null
        if ($claudeVer) {
            Write-Success "Claude Code is already installed: $claudeVer"
            $claudeInstalled = $true
            $claudeDetail = $claudeVer.ToString().Trim()
        }
    } catch {}

    if (-not $claudeInstalled) {
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
                $claudeDetail = $claudeVer.ToString().Trim()
            }
        } catch {}

        if (-not $claudeInstalled -and (Get-Command npm -ErrorAction SilentlyContinue)) {
            Write-Info "Installing Claude Code globally via npm (@anthropic-ai/claude-code)..."
            try {
                Start-Process cmd.exe -ArgumentList "/c", "npm install -g @anthropic-ai/claude-code" -NoNewWindow -PassThru -Wait | Out-Null
                Refresh-EnvPath
                $claudeVer = & claude --version 2>$null
                if ($claudeVer) {
                    Write-Success "Claude Code successfully installed via npm: $claudeVer"
                    $claudeInstalled = $true
                    $claudeDetail = $claudeVer.ToString().Trim()
                }
            } catch {}
        }
    }
    $results["Claude Code"] = @{ ok = $claudeInstalled; detail = $claudeDetail }

    # Always run the connector registration when Claude is installed (repairs existing broken entries)
    $claudeMcpOk = $false
    $claudeMcpDetail = "Skipped (Claude not installed)"
    if ($claudeInstalled) {
        if ($resolvedMcpExe) {
            Write-Info "Connecting Daybook MCP server ('reminders') to Claude Code..."
            try {
                & claude mcp remove --scope user reminders 2>$null | Out-Null
                & claude mcp add --scope user reminders -- "$resolvedMcpExe" mcp
                if ($LASTEXITCODE -eq 0) {
                    [Environment]::SetEnvironmentVariable("MCP_TIMEOUT", "90000", "User")
                    $env:MCP_TIMEOUT = "90000"
                    Write-Success "Daybook MCP server connected to Claude Code (with 'mcp' arg & 90s timeout)."
                    $claudeMcpOk = $true
                    $claudeMcpDetail = "Registered ('reminders' -> mcp)"
                } else {
                    Write-Err "claude mcp add exited with code $LASTEXITCODE."
                    $claudeMcpDetail = "claude mcp add failed (exit $LASTEXITCODE)"
                }
            } catch {
                Write-Err "Failed to register Claude MCP: $($_.Exception.Message)"
                $claudeMcpDetail = $_.Exception.Message
            }
        } else {
            Write-Err "Could not locate daybook-mcp.exe to register with Claude Code."
            $claudeMcpDetail = "daybook-mcp.exe not found"
        }
    }
    $results["Claude Daybook Link"] = @{ ok = $claudeMcpOk; detail = $claudeMcpDetail }
}

# -------------------------------------------------------------
# STEP 2B: GEMINI CLI + MCP CONNECTION
# -------------------------------------------------------------
if ($runGemini) {
    Write-Step "Checking Google Gemini CLI"
    $geminiDir = Join-Path $ToolsDir "gemini-cli"
    Add-To-UserPath $geminiDir
    Refresh-EnvPath

    $geminiInstalled = $false
    $geminiDetail = "Not installed"
    try {
        $geminiVer = & gemini --version 2>$null
        if ($geminiVer -and $LASTEXITCODE -eq 0) {
            Write-Success "Google Gemini CLI is already installed: $geminiVer"
            $geminiInstalled = $true
            $geminiDetail = $geminiVer.ToString().Trim()
        }
    } catch {}

    if (-not $geminiInstalled) {
        if (Get-Command npm -ErrorAction SilentlyContinue) {
            Write-Info "Installing Google Gemini CLI (@google/gemini-cli@$GeminiVersion) into $geminiDir..."
            try {
                New-Item -ItemType Directory -Force $geminiDir | Out-Null
                & npm install -g --prefix "$geminiDir" "@google/gemini-cli@$GeminiVersion" --no-fund --no-audit
                if ($LASTEXITCODE -ne 0) {
                    Write-Err "npm couldn't install Gemini CLI (exit $LASTEXITCODE)."
                    $geminiDetail = "npm exit $LASTEXITCODE"
                } else {
                    Add-To-UserPath $geminiDir
                    Refresh-EnvPath
                    $geminiCmd = Join-Path $geminiDir "gemini.cmd"
                    $geminiVer = if (Test-Path $geminiCmd) { & $geminiCmd --version 2>$null } else { & gemini --version 2>$null }
                    if ($geminiVer) {
                        Write-Success "Google Gemini CLI ready: $geminiVer"
                        $geminiInstalled = $true
                        $geminiDetail = $geminiVer.ToString().Trim()
                    } else {
                        Write-Err "Gemini CLI installed, but 'gemini --version' did not return a version."
                        $geminiDetail = "Verification failed"
                    }
                }
            } catch {
                Write-Err "Failed to install Gemini CLI: $($_.Exception.Message)"
                $geminiDetail = $_.Exception.Message
            }
        } else {
            Write-Err "npm is not available; cannot install Gemini CLI."
            $geminiDetail = "npm missing"
        }
    }
    $results["Gemini CLI"] = @{ ok = $geminiInstalled; detail = $geminiDetail }

    # Always register Daybook MCP in ~/.gemini/settings.json when running Gemini setup
    $geminiMcpOk = $false
    $geminiMcpDetail = "daybook-mcp.exe not found"
    if ($resolvedMcpExe) {
        Write-Info "Registering Daybook MCP server ('daybook') in ~/.gemini/settings.json..."
        if (Register-GeminiMcp -ExePath $resolvedMcpExe) {
            Write-Success "Daybook MCP server registered for Gemini CLI (90s timeout)."
            $geminiMcpOk = $true
            $geminiMcpDetail = "Registered ('daybook' -> mcp)"
        } else {
            $geminiMcpDetail = "Could not update settings.json"
        }
    } else {
        Write-Err "Could not locate daybook-mcp.exe for Gemini CLI."
    }
    $results["Gemini Daybook Link"] = @{ ok = $geminiMcpOk; detail = $geminiMcpDetail }
}

# -------------------------------------------------------------
# STEP 2C: ANTIGRAVITY (AGY) + MCP CONNECTION
# -------------------------------------------------------------
if ($runAgy) {
    Write-Step "Checking Google Antigravity (AGY)"
    $agyExe = Find-AgyExe
    if (-not $agyExe -and (Get-Command winget -ErrorAction SilentlyContinue)) {
        Write-Info "Installing Google Antigravity CLI via winget (Google.AntigravityCLI)..."
        try {
            $proc = Start-Process winget -ArgumentList "install", "--id", "Google.AntigravityCLI", "-e", "--silent", "--accept-package-agreements", "--accept-source-agreements" -NoNewWindow -PassThru -Wait
            Refresh-EnvPath
            $agyExe = Find-AgyExe
            if (-not $agyExe) { Write-Warn "winget finished (exit $($proc.ExitCode)) but agy.exe wasn't found yet - open a new terminal and try again." }
        } catch {
            Write-Warn "winget install of Antigravity CLI failed: $($_.Exception.Message)"
        }
    }
    $agyInstalled = $false
    $agyDetail = "Not installed"
    if ($agyExe) {
        Add-To-UserPath (Split-Path -Parent $agyExe)
        Refresh-EnvPath
        $agyInstalled = $true
        try {
            $agyVer = & $agyExe --version 2>$null
            $agyDetail = if ($agyVer) { ($agyVer | Select-Object -First 1).ToString().Trim() } else { $agyExe }
        } catch {
            $agyDetail = $agyExe
        }
        Write-Success "Google Antigravity (AGY) found: $agyDetail"
    } else {
        Write-Warn "Antigravity CLI (agy.exe) not found on PATH; configuring Daybook MCP config files in ~/.gemini so AGY connects automatically."
    }
    if ($Only -eq "agy" -or $agyInstalled) {
        $results["Antigravity (AGY)"] = @{ ok = $agyInstalled; detail = $agyDetail }
    }

    $agyMcpOk = $false
    $agyMcpDetail = "daybook-mcp.exe not found"
    if ($resolvedMcpExe) {
        Write-Info "Connecting Daybook MCP server ('daybook') to Antigravity (AGY)..."
        if (Register-AgyMcp -ExePath $resolvedMcpExe -AgyExe $agyExe) {
            Write-Success "Daybook MCP server connected to Antigravity (AGY) with 'mcp' argument."
            $agyMcpOk = $true
            $agyMcpDetail = "Registered ('daybook' -> mcp)"
        } else {
            $agyMcpDetail = "Could not update mcp_config.json"
        }
    } else {
        Write-Err "Could not locate daybook-mcp.exe for Antigravity (AGY)."
    }
    $results["AGY Daybook Link"] = @{ ok = $agyMcpOk; detail = $agyMcpDetail }
}

# -------------------------------------------------------------
# STEP 3 & 4: OLLAMA LOCAL AI + MODEL
# -------------------------------------------------------------
if ($runOllama) {
    Write-Step "Checking Ollama (Local AI Engine)"
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
                    $ollamaInstalled = $true
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
                    $ollamaInstalled = $true
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

    Write-Info "Verifying Ollama background service..."
    $ollamaRunning = $false
    if ($ollamaInstalled) {
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
    }
    $ollamaDetail = if ($ollamaRunning) { "Active (port 11434)" } elseif ($ollamaInstalled) { "Installed (service not responding)" } else { "Not installed" }
    $results["Ollama Local AI"] = @{ ok = $ollamaRunning; detail = $ollamaDetail }

    Write-Step "Model Recommendation for Your Hardware"
    if ([string]::IsNullOrWhiteSpace($Model)) {
        if (-not $hasDedicatedGpu -or $totalRamGB -lt 16) {
            $Model = "qwen3.5:2b"
            Write-Info "Laptop profile detected ($totalRamGB GB RAM, integrated graphics). Selecting lightweight model '$Model' (~1 GB)."
        } else {
            $Model = "qwen3.5:9b"
            Write-Info "Desktop/GPU profile detected ($totalRamGB GB RAM). Selecting standard 9B model '$Model'."
        }
    }

    if (-not $SkipModelPull) {
        $modelOk = $false
        $modelDetail = "Skipped (Ollama not running)"
        if ($ollamaRunning) {
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
                    $modelOk = $true
                    $modelDetail = "$Model (ready)"
                } else {
                    Write-Info "Pulling '$Model' for offline reminders, notes & chat..."
                    & ollama pull $Model
                    if ($LASTEXITCODE -eq 0) {
                        Write-Success "Model '$Model' downloaded successfully!"
                        $modelOk = $true
                        $modelDetail = "$Model (downloaded)"
                    } else {
                        Write-Err "Could not pull '$Model' (exit $LASTEXITCODE)."
                        $modelDetail = "Pull failed for $Model"
                    }
                }
            } catch {
                Write-Err "Model check/pull failed: $($_.Exception.Message)"
                $modelDetail = $_.Exception.Message
            }
        }
        $results["Local AI Model"] = @{ ok = $modelOk; detail = $modelDetail }
    }
}

# -------------------------------------------------------------
# STEP 5: TEST MCP HANDSHAKE
# -------------------------------------------------------------
if ($runClaude -or $runGemini -or $runAgy) {
    Write-Step "Testing Daybook MCP Connector Handshake"
    if ($resolvedMcpExe) {
        $sw = [System.Diagnostics.Stopwatch]::StartNew()
        $handshakeOk = Test-McpHandshake -ExePath $resolvedMcpExe -TimeoutMs 90000
        $sw.Stop()
        if ($handshakeOk) {
            Write-Success "Daybook MCP connector answered initialize in $([math]::Round($sw.Elapsed.TotalSeconds, 1))s."
            $results["Daybook Handshake"] = @{ ok = $true; detail = "Connected ($([math]::Round($sw.Elapsed.TotalSeconds, 1))s)" }
        } else {
            Write-Err "Daybook MCP connector did not answer initialize within 90s."
            $results["Daybook Handshake"] = @{ ok = $false; detail = "Handshake failed" }
        }
    } else {
        Write-Err "daybook-mcp.exe not found; could not verify MCP handshake."
        $results["Daybook Handshake"] = @{ ok = $false; detail = "daybook-mcp.exe not found" }
    }
}

# -------------------------------------------------------------
# STEP 6: FINAL SUMMARY
# -------------------------------------------------------------
$anyFailed = $false
foreach ($k in $results.Keys) {
    if (-not $results[$k].ok) { $anyFailed = $true; break }
}

if (-not $anyFailed) {
    Write-Host "`n================================================================" -ForegroundColor Green
    Write-Host "                AI STACK SETUP COMPLETE!                        " -ForegroundColor White
    Write-Host "================================================================" -ForegroundColor Green
} else {
    Write-Host "`n================================================================" -ForegroundColor Red
    Write-Host "           AI STACK SETUP FINISHED WITH ISSUES                  " -ForegroundColor White
    Write-Host "================================================================" -ForegroundColor Red
}

foreach ($k in $results.Keys) {
    $r = $results[$k]
    Show-Result $k $r.ok $r.detail
}

Write-Host "================================================================`n" -ForegroundColor Cyan

# Sign-in launch in the same terminal when run interactively for a specific tool
if (-not $NonInteractive) {
    if ($Only -eq "gemini" -and $results["Gemini CLI"] -and $results["Gemini CLI"].ok) {
        Write-Host "Choose 'Login with Google' for the free tier." -ForegroundColor Yellow
        & gemini
    } elseif ($Only -eq "claude" -and $results["Claude Code"] -and $results["Claude Code"].ok) {
        Write-Host "Starting Claude Code so you can sign in..." -ForegroundColor Yellow
        & claude
    } elseif ($Only -eq "agy" -and $agyExe) {
        Write-Host "Starting Antigravity (AGY)..." -ForegroundColor Yellow
        & $agyExe
    }
}

if ($anyFailed) { exit 1 } else { exit 0 }
