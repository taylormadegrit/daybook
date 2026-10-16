"""
Security and sanitization test suite for Daybook:
- Path traversal prevention
- Origin and Host header validation / IP restrictions
- Secret and credential word detection in note importer
- SQL injection resistance
- Safe file extension enforcement on upload endpoints
"""
import unittest
import io
import json
from reminders.web import app
from reminders import db, notes


class TestSecurity(unittest.TestCase):
    """Verifies security boundaries, sanitization, and leak protections."""

    @classmethod
    def setUpClass(cls):
        app.config["TESTING"] = True
        cls.client = app.test_client()

    def test_path_traversal_prevention(self):
        """Verifies attempts to traverse outside static and data directories fail with 404 or 400."""
        traversal_payloads = [
            "/app/../../daemon.pyw",
            "/app/..%2f..%2fdaemon.pyw",
            "/annotations/../../reminders/db.py",
            "/backgrounds/../../config.json",
        ]
        for url in traversal_payloads:
            res = self.client.get(url)
            self.assertIn(res.status_code, [404, 400, 301, 308], f"Path traversal not blocked for {url}")

    def test_secret_words_filtering(self):
        """Verifies that filenames containing credential markers are blocked by SECRET_WORDS regex."""
        dangerous_names = [
            "api_key.txt",
            "my_login_credentials.docx",
            "aws_token.md",
            "master_password.odt",
            "google_2fa_backup.txt",
            "secret_client_info.txt",
            "passwd_dump.txt",
        ]
        for name in dangerous_names:
            self.assertTrue(bool(notes.SECRET_WORDS.search(name)), f"Failed to detect secret in: {name}")

        safe_names = [
            "weekly_meeting.txt",
            "youtube_ideas.md",
            "workout_routine.txt",
            "project_daybook_tasks.docx",
        ]
        for name in safe_names:
            self.assertFalse(bool(notes.SECRET_WORDS.search(name)), f"False positive secret match on: {name}")

    def test_sql_injection_resistance(self):
        """Verifies SQL injection attempts in search queries, categories, and titles do not execute."""
        injections = [
            "' OR '1'='1",
            "'; DROP TABLE reminders; --",
            "\" OR \"\"=\"",
            "1' UNION SELECT 1, 2, 3, 4, 5, 6, 7, 8, 9, 10 --",
        ]
        for inj in injections:
            # 1. In notes search
            res = self.client.get(f"/api/notes?q={inj}&category={inj}")
            self.assertEqual(res.status_code, 200)

            # 2. In reminder query
            res_rem = self.client.post("/api/reminders",
                                       data=json.dumps({"text": f"SQL Test {inj}", "due": "2026-10-25T10:00:00", "category": inj}),
                                       content_type="application/json")
            self.assertEqual(res_rem.status_code, 200)
            rid = res_rem.get_json()["id"]

            # Verify table still exists and data is safe
            r = db.get(rid)
            self.assertIsNotNone(r)
            self.assertEqual(r["text"], f"SQL Test {inj}")
            db.delete(rid)

    def test_upload_extension_restriction(self):
        """Verifies that non-whitelisted extensions (e.g. .exe, .bat, .py) are rejected."""
        forbidden_files = ["malware.exe", "script.bat", "exploit.py", "shell.php", "setup.msi"]
        for fname in forbidden_files:
            data = {"file": (io.BytesIO(b"fake dangerous binary"), fname)}
            res = self.client.post("/api/home/background", data=data, content_type="multipart/form-data")
            self.assertEqual(res.status_code, 400)
            self.assertIn("error", res.get_json())

    def test_host_header_security(self):
        """Verifies host filtering rejects untrusted external domain hosts when TESTING is False."""
        app.config["TESTING"] = False
        try:
            prod_client = app.test_client()

            # Malicious external host
            res_evil = prod_client.get("/api/meta", headers={"Host": "attacker.com"})
            self.assertEqual(res_evil.status_code, 403)

            # Legitimate local and LAN hosts
            res_local = prod_client.get("/api/meta", headers={"Host": "127.0.0.1:8503"})
            self.assertEqual(res_local.status_code, 200)

            res_lan = prod_client.get("/api/meta", headers={"Host": "192.168.1.150:8503"})
            self.assertEqual(res_lan.status_code, 200)
        finally:
            app.config["TESTING"] = True


if __name__ == "__main__":
    unittest.main()
