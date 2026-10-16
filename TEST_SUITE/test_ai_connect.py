"""Tests for install-ai-stack.ps1 (Register-GeminiMcp, params), claude_link stack_status, and MCP proxy/fast init."""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import mcp_server
from reminders import claude_link, web

ROOT = Path(__file__).resolve().parent.parent
PS_SCRIPT = ROOT / "install-ai-stack.ps1"


class InstallerPowerShellTest(unittest.TestCase):
    def test_script_syntax_and_params(self):
        """Verify install-ai-stack.ps1 parses cleanly in PowerShell and exposes expected parameters."""
        cmd = f"$ErrorActionPreference = 'Stop'; (Get-Command '{PS_SCRIPT}').Parameters.Keys -join ','"
        r = subprocess.run(["powershell.exe", "-NoProfile", "-Command", cmd], capture_output=True, text=True, timeout=15)
        self.assertEqual(r.returncode, 0, r.stderr)
        params = r.stdout.strip().split(",")
        for expected in ("SkipModelPull", "Model", "NonInteractive", "Only", "McpExe", "ToolsDir", "GeminiVersion"):
            self.assertIn(expected, params)

    def test_register_gemini_mcp_merges_without_bom_and_preserves_other_servers(self):
        """Register-GeminiMcp merges daybook entry with args=['mcp'] and timeout=90000 without BOM."""
        with tempfile.TemporaryDirectory() as tmp:
            fake_exe = Path(tmp) / "daybook-mcp.exe"
            fake_exe.write_bytes(b"MZ")
            gem_dir = Path(tmp) / ".gemini"
            gem_dir.mkdir()
            settings_file = gem_dir / "settings.json"
            settings_file.write_text(
                json.dumps({"mcpServers": {"other": {"command": "node", "args": ["srv.js"]}}, "theme": "dark"}),
                encoding="utf-8",
            )
            ps_code = f"""
            $env:USERPROFILE = '{tmp}'
            $ast = [System.Management.Automation.Language.Parser]::ParseFile('{PS_SCRIPT}', [ref]$null, [ref]$null)
            $funcs = $ast.FindAll({{ param($n) $n -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -in @('Write-Err','Register-GeminiMcp') }}, $true)
            foreach ($f in $funcs) {{ Invoke-Expression $f.Extent.Text }}
            $ok = Register-GeminiMcp -ExePath '{fake_exe}'
            if (-not $ok) {{ exit 2 }}
            """
            r = subprocess.run(["powershell.exe", "-NoProfile", "-Command", ps_code], capture_output=True, text=True, timeout=15)
            self.assertEqual(r.returncode, 0, r.stderr + r.stdout)

            raw_bytes = settings_file.read_bytes()
            self.assertFalse(raw_bytes.startswith(b"\xef\xbb\xbf"), "settings.json must not have a UTF-8 BOM")
            data = json.loads(raw_bytes.decode("utf-8"))
            self.assertEqual(data["theme"], "dark")
            self.assertIn("other", data["mcpServers"])
            self.assertEqual(
                data["mcpServers"]["daybook"],
                {"command": str(fake_exe), "args": ["mcp"], "timeout": 90000},
            )
            self.assertTrue((gem_dir / "settings.json.daybook-backup").exists())

    def test_register_gemini_mcp_leaves_commented_json_untouched(self):
        """If settings.json has comments / invalid JSON, Register-GeminiMcp returns false and leaves it untouched."""
        with tempfile.TemporaryDirectory() as tmp:
            fake_exe = Path(tmp) / "daybook-mcp.exe"
            fake_exe.write_bytes(b"MZ")
            gem_dir = Path(tmp) / ".gemini"
            gem_dir.mkdir()
            settings_file = gem_dir / "settings.json"
            original = '// user comment\n{\n  "theme": "dark"\n}\n'
            settings_file.write_text(original, encoding="utf-8")

            ps_code = f"""
            $env:USERPROFILE = '{tmp}'
            $ast = [System.Management.Automation.Language.Parser]::ParseFile('{PS_SCRIPT}', [ref]$null, [ref]$null)
            $funcs = $ast.FindAll({{ param($n) $n -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -in @('Write-Err','Register-GeminiMcp') }}, $true)
            foreach ($f in $funcs) {{ Invoke-Expression $f.Extent.Text }}
            $ok = Register-GeminiMcp -ExePath '{fake_exe}'
            if ($ok) {{ exit 3 }}
            """
            r = subprocess.run(["powershell.exe", "-NoProfile", "-Command", ps_code], capture_output=True, text=True, timeout=15)
            self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
            self.assertEqual(settings_file.read_text(encoding="utf-8"), original)

    def test_powershell_mcp_handshake_sends_no_bom(self):
        """Test-McpHandshake in install-ai-stack.ps1 must set UTF-8 without BOM on Console::InputEncoding so stdin has no BOM."""
        text = PS_SCRIPT.read_text(encoding="utf-8")
        self.assertIn("[Console]::InputEncoding = New-Object System.Text.UTF8Encoding $false", text)

    def test_register_agy_mcp_merges_without_bom_and_preserves_other_servers(self):
        """Register-AgyMcp merges daybook entry with args=['mcp'] into both mcp_config.json files without BOM."""
        with tempfile.TemporaryDirectory() as tmp:
            fake_exe = Path(tmp) / "daybook-mcp.exe"
            fake_exe.write_bytes(b"MZ")
            cfg_dir = Path(tmp) / ".gemini" / "config"
            cfg_dir.mkdir(parents=True)
            cfg_file1 = cfg_dir / "mcp_config.json"
            cfg_file1.write_text(
                json.dumps({"mcpServers": {"rea": {"command": "rea-mcp", "args": []}}}),
                encoding="utf-8",
            )
            cfg_file2 = Path(tmp) / ".gemini" / "antigravity" / "mcp_config.json"

            ps_code = f"""
            $env:USERPROFILE = '{tmp}'
            $ast = [System.Management.Automation.Language.Parser]::ParseFile('{PS_SCRIPT}', [ref]$null, [ref]$null)
            $funcs = $ast.FindAll({{ param($n) $n -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -in @('Write-Err','Write-Step','Write-Ok','Merge-AgyMcpFile','Register-AgyMcp') }}, $true)
            foreach ($f in $funcs) {{ Invoke-Expression $f.Extent.Text }}
            $ok = Register-AgyMcp -ExePath '{fake_exe}' -AgyExe $null
            if (-not $ok) {{ exit 2 }}
            """
            r = subprocess.run(["powershell.exe", "-NoProfile", "-Command", ps_code], capture_output=True, text=True, timeout=15)
            self.assertEqual(r.returncode, 0, r.stderr + r.stdout)

            for f in (cfg_file1, cfg_file2):
                self.assertTrue(f.exists())
                raw_bytes = f.read_bytes()
                self.assertFalse(raw_bytes.startswith(b"\xef\xbb\xbf"), f"{f} must not have a UTF-8 BOM")
                data = json.loads(raw_bytes.decode("utf-8"))
                self.assertEqual(
                    data["mcpServers"]["daybook"],
                    {"command": str(fake_exe), "args": ["mcp"]},
                )
            self.assertIn("rea", json.loads(cfg_file1.read_text(encoding="utf-8"))["mcpServers"])
            self.assertTrue((cfg_dir / "mcp_config.json.daybook-backup").exists())


class StackStatusAndTrustTest(unittest.TestCase):
    def test_entry_args_ok_detects_missing_mcp_arg(self):
        self.assertFalse(claude_link._entry_args_ok({"command": r"C:\Daybook\daybook-mcp.exe", "args": []}))
        self.assertTrue(claude_link._entry_args_ok({"command": r"C:\Daybook\daybook-mcp.exe", "args": ["mcp"]}))
        self.assertTrue(claude_link._entry_args_ok({"command": "python.exe", "args": [r"D:\projects\local-reminders\mcp_server.py"]}))

    def test_gemini_trust_and_stack_status_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake_home = Path(tmp)
            gem_dir = fake_home / ".gemini"
            gem_dir.mkdir()
            (gem_dir / "settings.json").write_text(
                json.dumps({
                    "mcpServers": {"daybook": {"command": "daybook-mcp.exe", "args": ["mcp"], "timeout": 90000}},
                    "security": {"auth": {"selectedType": "oauth-personal"}},
                }),
                encoding="utf-8",
            )
            (fake_home / ".claude.json").write_text(
                json.dumps({
                    "mcpServers": {"reminders": {"command": "daybook-mcp.exe", "args": []}}
                }),
                encoding="utf-8",
            )
            with mock.patch.object(Path, "home", return_value=fake_home), \
                    mock.patch.object(claude_link, "test_mcp_handshake", return_value={"handshake_ok": True, "startup_ms": 320}):
                self.assertFalse(claude_link.gemini_trust_status())
                self.assertTrue(claude_link.set_gemini_trust(True))
                self.assertTrue(claude_link.gemini_trust_status())

                tf_data = json.loads((gem_dir / "trustedFolders.json").read_text(encoding="utf-8"))
                expected_key = str(fake_home).replace("\\", "/").lower()
                self.assertEqual(tf_data.get(expected_key), "TRUST_FOLDER")

                st = claude_link.stack_status()
                self.assertTrue(st["claude"]["registered"])
                self.assertFalse(st["claude"]["args_ok"])
                self.assertFalse(st["claude"]["connected"])

                self.assertTrue(st["gemini"]["registered"])
                self.assertTrue(st["gemini"]["args_ok"])
                self.assertTrue(st["gemini"]["connected"])
                self.assertTrue(st["gemini"]["signed_in"])
                self.assertTrue(st["gemini"]["trusted_home"])
                self.assertIn("agy", st)
                self.assertFalse(st["agy"]["registered"])
                self.assertFalse(st["agy"]["connected"])
                self.assertEqual(st["mcp"], {"handshake_ok": True, "startup_ms": 320})

                # Test connect_agy() and disconnect("agy") inside fake_home
                with mock.patch.object(claude_link, "_agy_exe", return_value=None):
                    claude_link.connect_agy()
                st2 = claude_link.stack_status()
                self.assertTrue(st2["agy"]["registered"])
                self.assertTrue(st2["agy"]["args_ok"])
                self.assertTrue(st2["agy"]["connected"])

                claude_link.disconnect("agy")
                st3 = claude_link.stack_status()
                self.assertFalse(st3["agy"]["registered"])
                self.assertFalse(st3["agy"]["connected"])

    def test_live_mcp_handshake_is_fast(self):
        res = claude_link.test_mcp_handshake(force=True, timeout=15.0)
        self.assertTrue(res["handshake_ok"], res)
        self.assertLess(res["startup_ms"], 5000, f"Handshake took {res['startup_ms']} ms (goal < 5000 ms)")


class McpForwardingTest(unittest.TestCase):
    def test_returns_clear_message_when_daybook_not_running(self):
        with mock.patch.object(mcp_server, "_ensure_backend", return_value=False):
            out = mcp_server.day_schedule("")
            self.assertEqual(out, "Daybook isn't running. Open Daybook and try again.")

    def test_web_api_mcp_tool_endpoint_executes_tool(self):
        client = web.app.test_client()
        resp = client.post("/api/mcp/tool", json={"tool": "day_schedule", "args": {"date": "2026-10-16"}})
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data["ok"])
        self.assertIn("Oct 16", data["result"])


if __name__ == "__main__":
    unittest.main()
