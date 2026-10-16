"""
daybook-mcp.exe is a copy of the packaged backend. Started without an argument it used to run the
daemon, which exits silently when Daybook is already running, so Claude Code / Gemini CLI saw
"connection closed" (1.7.9). It must always start the MCP server.
"""
import sys
import unittest
from unittest import mock

import backend_main


class McpEntryTest(unittest.TestCase):
    def _run(self, executable, argv):
        with mock.patch.object(sys, "executable", executable), \
                mock.patch.object(sys, "argv", list(argv)), \
                mock.patch.object(backend_main.paths, "FROZEN", False), \
                mock.patch.object(backend_main.runpy, "run_path") as run_path:
            backend_main.main()
        return run_path.call_args[0][0]

    def test_mcp_exe_without_argument_runs_mcp_server(self):
        script = self._run(r"C:\Daybook\resources\backend\daybook-mcp.exe", ["daybook-mcp.exe"])
        self.assertTrue(script.endswith("mcp_server.py"), script)

    def test_mcp_exe_with_mcp_argument_runs_mcp_server(self):
        script = self._run(r"C:\Daybook\resources\backend\daybook-mcp.exe", ["daybook-mcp.exe", "mcp"])
        self.assertTrue(script.endswith("mcp_server.py"), script)

    def test_backend_exe_without_argument_still_runs_daemon(self):
        script = self._run(r"C:\Daybook\resources\backend\daybook-backend.exe", ["daybook-backend.exe"])
        self.assertTrue(script.endswith("daemon.pyw"), script)

    def test_backend_exe_arcade_mode_runs_arcade(self):
        script = self._run(r"C:\Daybook\resources\backend\daybook-backend.exe", ["daybook-backend.exe", "arcade"])
        self.assertTrue(script.endswith("arcade.py"), script)


if __name__ == "__main__":
    unittest.main()
