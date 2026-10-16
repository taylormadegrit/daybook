# Daybook Patch Notes & Implementation Spec: Google AI & Antigravity (AGY) Integration

**Target Application:** Daybook (Windows Desktop App & 1-Click AI Stack)  
**Target Audience:** Development Team / Autonomous AI Coding Agent  
**Goal:** Automate 1-click installation, terminal execution, and MCP tool connection for **Google Gemini CLI** and **Antigravity CLI (`agy`)**.

---

## 1. Executive Summary & Root Cause Analysis

When a user attempts to run or connect Google AI models (**Gemini CLI** and **Antigravity AGY**) in Daybook, four primary failure points occur on default Windows systems:

### Root Causes
1. **PowerShell Script Execution Policy (`PSSecurityException`)**:
   * Daybook's default terminal shell is PowerShell (`powershell.exe`).
   * On standard Windows client machines, `ExecutionPolicy` is `Restricted` or `Undefined`.
   * When npm installs `@google/gemini-cli`, it generates `gemini.ps1`. Attempting to run `gemini` in PowerShell triggers:
     ```text
     gemini : File C:\Users\Taylor\AppData\Local\Programs\nodejs\gemini.ps1 cannot be loaded 
     because running scripts is disabled on this system. (PSSecurityException)
     ```
2. **`whichExe` Extension Precedence Bug (`main.js`)**:
   * Daybook’s `whichExe(name)` searched extensions in the order: `["", ".exe", ".cmd", ".bat"]`.
   * In `AppData\Local\Programs\nodejs`, npm generates both an extensionless Unix script (`gemini`) and a Windows batch script (`gemini.cmd`).
   * Because `""` came first, `whichExe("gemini")` returned the extensionless file (`...\nodejs\gemini`).
   * When Daybook spawned the terminal preset via `cmd.exe /k "...\nodejs\gemini"`, Windows `cmd.exe` failed with:
     ```text
     '...\gemini' is not recognized as an internal or external command, operable program or batch file.
     ```
3. **Missing Tool PATHs & Presets for Antigravity (`agy`)**:
   * Antigravity installs its binary to `%LOCALAPPDATA%\agy\bin\agy.exe`.
   * Daybook's internal terminal environment (`extraPaths` in `main.js`) injected Claude, Node, and Ollama paths, but omitted `agy\bin`.
   * Daybook's `termProfiles` had no profile or preset for Antigravity AGY in the UI menu.
4. **UTF-8 BOM in `mcp_config.json`**:
   * Standard PowerShell `Set-Content -Encoding UTF8` prepends a Byte Order Mark (`\uFEFF`).
   * Antigravity's Go-based JSON parser fails on BOMs (`invalid character '\ufeff' looking for beginning of value`). MCP config must be written as UTF-8 **without BOM**.

---

## 2. Specification of Changes

### A. 1-Click AI Stack Installer (`install-ai-stack.ps1`)

**Location:** `backend/_internal/install-ai-stack.ps1` (and `install-ai-stack.ps1` at root)

#### 1. Set Execution Policy Automatically (Non-Elevated)
At the very top of `install-ai-stack.ps1`, add a check and fix for the CurrentUser execution policy so local npm scripts and installers run smoothly:

```powershell
# Ensure PowerShell scripts can run for the current user without requiring Administrator rights
try {
    $policy = Get-ExecutionPolicy -Scope CurrentUser
    if ($policy -in @("Undefined", "Restricted")) {
        Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser -Force -ErrorAction SilentlyContinue
    }
} catch {}
```

#### 2. Update `Refresh-EnvPath` to Include AGY
Add the Antigravity paths to the candidate list in `Refresh-EnvPath`:

```powershell
    $candidates = @(
        "$env:LOCALAPPDATA\Programs\nodejs",
        "$env:ProgramFiles\nodejs",
        "$env:APPDATA\npm",
        "$env:USERPROFILE\.local\bin",
        "$env:USERPROFILE\.claude\bin",
        "$env:LOCALAPPDATA\agy\bin",
        "$env:USERPROFILE\.gemini\antigravity-ide\bin",
        "$env:LOCALAPPDATA\Programs\Antigravity IDE\bin",
        "$env:LOCALAPPDATA\Programs\Ollama",
        "$env:LOCALAPPDATA\Programs\Ollama\bin"
    )
```

#### 3. Install & Verify Google Gemini CLI
Ensure the Gemini CLI wrapper is verified and installed:

```powershell
# -------------------------------------------------------------
# GOOGLE GEMINI CLI
# -------------------------------------------------------------
Write-Step "Checking Google Gemini CLI"
$geminiInstalled = $false
try {
    $geminiVer = & gemini.cmd --version 2>$null
    if (-not $geminiVer) { $geminiVer = & gemini --version 2>$null }
    if ($geminiVer) {
        Write-Success "Google Gemini CLI is already installed: $geminiVer"
        $geminiInstalled = $true
    }
} catch {}

if (-not $geminiInstalled -and (Get-Command npm -ErrorAction SilentlyContinue)) {
    Write-Info "Installing Google Gemini CLI globally via npm (@google/gemini-cli)..."
    try {
        Start-Process cmd.exe -ArgumentList "/c", "npm install -g @google/gemini-cli" -NoNewWindow -PassThru -Wait | Out-Null
        Refresh-EnvPath
        $geminiVer = & gemini.cmd --version 2>$null
        if ($geminiVer) {
            Write-Success "Google Gemini CLI successfully installed: $geminiVer"
            $geminiInstalled = $true
        }
    } catch {
        Write-Warn "Could not install Gemini CLI: $($_.Exception.Message)"
    }
}
```

#### 4. Auto-Connect Daybook MCP to Gemini CLI and Antigravity AGY
Add registration logic so that when `install-ai-stack.ps1` runs, it connects Daybook's MCP server (`daybook-mcp.exe`) to **both** Gemini and Antigravity:

```powershell
# Locate Daybook MCP executable
$mcpCandidates = @(
    "$PSScriptRoot\daybook-mcp.exe",
    "$PSScriptRoot\backend\daybook-mcp.exe",
    "$env:LOCALAPPDATA\Programs\Daybook\resources\backend\daybook-mcp.exe"
)
$mcpExe = $mcpCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1

if ($mcpExe) {
    # 1. Connect to Gemini CLI
    if ($geminiInstalled) {
        try {
            Write-Info "Connecting Daybook MCP server to Gemini CLI..."
            Start-Process cmd.exe -ArgumentList "/c", "gemini mcp add daybook `"$mcpExe`"" -NoNewWindow -PassThru -Wait | Out-Null
            Write-Success "Daybook MCP server connected to Gemini CLI."
        } catch {}
    }

    # 2. Connect to Antigravity CLI (AGY) & Antigravity IDE
    try {
        $geminiConfigDir = "$env:USERPROFILE\.gemini\config"
        if (-not (Test-Path $geminiConfigDir)) {
            New-Item -ItemType Directory -Path $geminiConfigDir -Force | Out-Null
        }
        $mcpConfigPath = "$geminiConfigDir\mcp_config.json"
        
        $configObj = @{ mcpServers = @{} }
        if (Test-Path $mcpConfigPath) {
            try {
                $raw = [System.IO.File]::ReadAllText($mcpConfigPath)
                if (-not [string]::IsNullOrWhiteSpace($raw)) {
                    $configObj = $raw | ConvertFrom-Json
                }
            } catch {}
        }
        
        if (-not $configObj.mcpServers) { $configObj | Add-Member -MemberType NoteProperty -Name "mcpServers" -Value @{} }
        
        $daybookConfig = @{
            command = $mcpExe
            args = @()
        }
        $configObj.mcpServers.daybook = $daybookConfig
        
        # MUST write as UTF-8 WITHOUT BOM for Go JSON parser
        $jsonStr = $configObj | ConvertTo-Json -Depth 5
        [System.IO.File]::WriteAllText($mcpConfigPath, $jsonStr, (New-Object System.Text.UTF8Encoding($false)))
        Write-Success "Daybook MCP server connected to Antigravity (AGY)."
    } catch {
        Write-Warn "Could not update Antigravity mcp_config.json: $($_.Exception.Message)"
    }
}
```

---

### B. Electron Main Process (`main.js`)

**Location:** `main.js` (inside `app.asar` / Electron source)

#### 1. Fix `whichExe` Search Precedence
Change extension loop to look for Windows executables (`.exe`, `.cmd`, `.bat`) *before* extensionless files:

```diff
  function whichExe(name) {
    const homedir = require("os").homedir();
    const dirs = (process.env.PATH || "").split(";").filter(Boolean).concat([
      path.join(TOOLS_DIR, "gemini-cli"),
      path.join(homedir, ".local", "bin"),
      path.join(homedir, ".claude", "bin"),
+     path.join(process.env.LOCALAPPDATA || "", "agy", "bin"),
+     path.join(homedir, ".gemini", "antigravity-ide", "bin"),
      path.join(process.env.LOCALAPPDATA || "", "Programs", "nodejs"),
      path.join(process.env.APPDATA || "", "npm"),
      "C:\\Program Files\\nodejs",
      "C:\\Program Files (x86)\\nodejs",
      path.join(process.env.LOCALAPPDATA || "", "Programs", "Ollama")
    ]);
-   for (const d of dirs) for (const ext of ["", ".exe", ".cmd", ".bat"]) { const f = path.join(d, name + ext); try { if (fs.statSync(f).isFile()) return f; } catch {} }
+   for (const d of dirs) for (const ext of [".exe", ".cmd", ".bat", ""]) { const f = path.join(d, name + ext); try { if (fs.statSync(f).isFile()) return f; } catch {} }
    return null;
  }
```

#### 2. Add AGY to `termProfiles()`
```diff
  function termProfiles() {
    const first = (...c) => c.find(f => f && fs.existsSync(f)) || null;
    const pwsh = whichExe("pwsh"), ps = pwsh || "powershell.exe";
    const claude = whichExe("claude"), gemini = whichExe("gemini"), ollama = whichExe("ollama") || first("D:\\Applications\\Ollama\\ollama.exe");
+   const agy = whichExe("agy");
    return [
      {id: "pwsh", name: "PowerShell", group: "Shells", ok: true},
      {id: "cmd", name: "Command Prompt", group: "Shells", ok: true},
      {id: "bash", name: "Git Bash", group: "Shells", ok: !!gitBash},
      {id: "wsl", name: "WSL (Linux)", group: "Shells", ok: !!whichExe("wsl")},
      {id: "ai-stack", name: "⚡ 1-Click AI Stack (Claude + Ollama + Node)", group: "AI", ok: true, hint: "1-Click automated installer for Node.js, Claude Code CLI and Ollama."},
      {id: "claude", name: "Claude Code", group: "AI", ok: !!claude, hint: "Install Claude Code from claude.ai/download, then sign in once in this terminal."},
      {id: "gemini", name: "Gemini CLI", group: "AI", ok: !!gemini, hint: "Not installed yet — Daybook can install it (Node.js needed), then sign in with Google in this terminal."},
+     {id: "agy", name: "Antigravity (AGY)", group: "AI", ok: !!agy, hint: "Google Antigravity autonomous agent CLI."},
      {id: "ollama", name: "Local AI (Ollama)", group: "AI", ok: !!ollama, hint: "Install Ollama from ollama.com, then pull a model."},
      {id: "emacs", name: emacsHome ? "Emacs (your Doom setup)" : "Emacs", group: "Tools", ok: !!emacs, hint: "Install Emacs (winget install GNU.Emacs)."},
      {id: "orca", name: "Orca", group: "Tools", ok: !!orca},
      {id: "arcade", name: "8-Bit Arcade (Snake, Pong, Galactica)", group: "Tools", ok: true},
-   ].map(p => ({...p, _ps: ps, _emacs: emacs, _emacsHome: emacsHome, _bash: gitBash, _orca: orca, _claude: claude, _gemini: gemini, _ollama: ollama}));
+   ].map(p => ({...p, _ps: ps, _emacs: emacs, _emacsHome: emacsHome, _bash: gitBash, _orca: orca, _claude: claude, _gemini: gemini, _agy: agy, _ollama: ollama}));
  }
```

#### 3. Add `agy` Command Spawn in `termCommand()`
```javascript
case "agy":
  return prof._agy ? ["cmd.exe", ["/k", `"${prof._agy}"`]]
    : inPs(`Write-Host 'Antigravity CLI (AGY) is not installed.' -ForegroundColor Yellow; Write-Host 'Please install Antigravity to use AGY.' -ForegroundColor Cyan`);
```

#### 4. Add `agy` to Terminal `extraPaths`
```diff
    const extraPaths = [
      path.join(TOOLS_DIR, "gemini-cli"),
      path.join(homedir, ".local", "bin"),
      path.join(homedir, ".claude", "bin"),
+     path.join(process.env.LOCALAPPDATA || "", "agy", "bin"),
+     path.join(homedir, ".gemini", "antigravity-ide", "bin"),
+     path.join(process.env.LOCALAPPDATA || "", "Programs", "Antigravity IDE", "bin"),
      path.join(process.env.APPDATA || "", "npm"),
      path.join(process.env.LOCALAPPDATA || "", "Programs", "nodejs"),
      "C:\\Program Files\\nodejs",
      "C:\\Program Files (x86)\\nodejs",
      path.join(process.env.LOCALAPPDATA || "", "Programs", "Ollama")
    ].filter(p => p && fs.existsSync(p));
```

---

### C. Frontend UI (`web/app/terminal.js`)

**Location:** `resources/backend/_internal/web/app/terminal.js`

#### 1. Add Icon for AGY
Update `T_ICON` mapping:
```javascript
const T_ICON = {
  claude: ["🪸", "#d97757"],
  gemini: ["✦", "#6aa8ff"],
  agy: ["🪐", "#4285f4"],
  ollama: ["🦙", "#3ee0a0"],
  "ai-stack": ["⚡", "#f7b731"],
  pwsh: [">_", "#9aa4b2"],
  cmd: ["C:", "#9aa4b2"],
  bash: ["$", "#98c379"],
  wsl: ["🐧", "#e5c07b"],
  emacs: ["e", "#c678dd"],
  orca: ["🐋", "#56b6c2"],
  arcade: ["👾", "#ffbe5c"]
};
```

#### 2. Update Preset Menu Item Handler
In `termAddMenu`:
```javascript
const item = p => {
  if (p.id === "claude" && !p.ok) return {t: "Claude Code (1-Click Install)", i: "plus", run: () => termNew("claude", {cwd})};
  if (p.id === "gemini" && !p.ok) return {t: "Gemini CLI — install & sign in", i: "plus", run: () => termNew("gemini", {cwd})};
  if (p.id === "agy" && !p.ok) return {t: "Antigravity (AGY) — install", i: "plus", run: () => termNew("agy", {cwd})};
  return {t: p.name, i: {claude: "spark", gemini: "spark", agy: "spark", emacs: "pen", orca: "zap", arcade: "gamepad"}[p.id] || "chip", off: !p.ok, run: () => termNew(p.id, {cwd})};
};
```

---

## 3. Verification Checklist for New Installations

| Step | Action | Expected Result |
| :--- | :--- | :--- |
| **1** | Run `install-ai-stack.ps1` | Installs Node.js, Gemini CLI, checks AGY, sets ExecutionPolicy, registers `daybook-mcp.exe` in both CLIs |
| **2** | Check `agy mcp list` | Shows `daybook (stdio, enabled)` pointing to `daybook-mcp.exe` |
| **3** | Check `gemini mcp list` | Shows `daybook: ...\daybook-mcp.exe (Connected)` |
| **4** | Open Daybook Terminal (`Ctrl+\``) | Default PowerShell opens; typing `gemini` launches Gemini CLI; typing `agy` launches Antigravity |
| **5** | Click `+` menu in Terminal | "Gemini CLI" launches `gemini.cmd` without file-not-found error; "Antigravity (AGY)" launches `agy.exe` |
