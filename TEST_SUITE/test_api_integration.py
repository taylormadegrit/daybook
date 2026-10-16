"""
Integration tests for Daybook Flask API endpoints using Flask test_client.
Verifies REST API responses, status codes, JSON structure, and database persistence.
"""
import unittest
import json
from reminders.web import app, VERSION


class TestAPIIntegration(unittest.TestCase):
    """Integration test suite for Daybook API endpoints."""

    @classmethod
    def setUpClass(cls):
        app.config["TESTING"] = True
        cls.client = app.test_client()

    def test_meta_endpoint(self):
        """Verify /api/meta returns valid metadata and version."""
        res = self.client.get("/api/meta")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIsNotNone(data)
        self.assertEqual(data.get("version"), VERSION)
        self.assertIn("categories", data)
        self.assertIn("templates", data)

    def test_status_endpoint(self):
        """Verify /api/status returns database counts and health metrics."""
        res = self.client.get("/api/status")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn("started", data)
        self.assertEqual(data.get("version"), VERSION)
        data = res.get_json()
        self.assertIn("counts", data)
        self.assertIn("reminders", data["counts"])
        self.assertIn("notes", data["counts"])

    def test_settings_get_and_patch(self):
        """Verify /api/settings retrieves and updates configuration."""
        res = self.client.get("/api/settings")
        self.assertEqual(res.status_code, 200)
        settings = res.get_json()
        self.assertIsInstance(settings, dict)

        # Update a test setting key (startup_view)
        patch_res = self.client.patch("/api/settings",
                                      data=json.dumps({"startup_view": "apps:gemini"}),
                                      content_type="application/json")
        self.assertEqual(patch_res.status_code, 200)

        # Verify the key persisted
        verify_res = self.client.get("/api/settings")
        updated = verify_res.get_json()
        self.assertEqual(updated.get("startup_view"), "apps:gemini")

    def test_reminders_crud_lifecycle(self):
        """Verify full lifecycle of a reminder: create, list, mark done, delete."""
        # 1. Create reminder
        create_res = self.client.post("/api/reminders",
                                      data=json.dumps({"text": "Automated Backtest Task", "due": "2026-12-31 12:00:00"}),
                                      content_type="application/json")
        self.assertIn(create_res.status_code, [200, 201])
        created = create_res.get_json()
        rid = created.get("id") or (created.get("reminder") or {}).get("id")
        self.assertIsNotNone(rid, "Created reminder should have an ID")

        # 2. List reminders and check presence
        list_res = self.client.get("/api/reminders")
        self.assertEqual(list_res.status_code, 200)
        reminders = list_res.get_json()
        found = any(r.get("id") == rid for r in reminders)
        self.assertTrue(found, "Created reminder must be present in reminders list")

        # 3. Mark done
        done_res = self.client.post(f"/api/reminders/{rid}/done")
        self.assertEqual(done_res.status_code, 200)

        # 4. Clean up / Delete
        del_res = self.client.delete(f"/api/reminders/{rid}")
        self.assertEqual(del_res.status_code, 200)

    def test_notes_crud_lifecycle(self):
        """Verify full lifecycle of a note: create, retrieve, patch, delete."""
        # 1. Create note
        create_res = self.client.post("/api/notes",
                                      data=json.dumps({"title": "Backtest Note", "body": "Testing notes API lifecycle."}),
                                      content_type="application/json")
        self.assertIn(create_res.status_code, [200, 201])
        created = create_res.get_json()
        nid = created.get("id") or (created.get("note") or {}).get("id")
        self.assertIsNotNone(nid)

        # 2. Retrieve note
        get_res = self.client.get(f"/api/notes/{nid}")
        self.assertEqual(get_res.status_code, 200)
        note = get_res.get_json()
        self.assertEqual(note.get("title"), "Backtest Note")

        # 3. Patch note
        patch_res = self.client.patch(f"/api/notes/{nid}",
                                      data=json.dumps({"body": "Updated test content."}),
                                      content_type="application/json")
        self.assertEqual(patch_res.status_code, 200)

        # 4. Delete note
        del_res = self.client.delete(f"/api/notes/{nid}")
        self.assertEqual(del_res.status_code, 200)

    def test_categories_endpoint(self):
        """Verify /api/categories returns default categories."""
        res = self.client.get("/api/categories")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIsInstance(data, (list, dict))

    def test_clock_endpoint(self):
        """Verify /api/clock returns time information and world clocks."""
        res = self.client.get("/api/clock")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIsNotNone(data)

    def test_localsend_status_endpoint(self):
        """Verify /api/localsend/status returns valid JSON structure."""
        res = self.client.get("/api/localsend/status")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn("installed", data)
        self.assertIn("running", data)
        self.assertIn("port", data)
        self.assertEqual(data.get("port"), 53317)
        self.assertIn("lan_ip", data)

    def test_claude_to_gemini_export(self):
        """Verify /api/ai/claude-to-gemini generates exportable prompt context."""
        res = self.client.get("/api/ai/claude-to-gemini")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get("ok"))
        self.assertIn("gemini_prompt", data)
        self.assertGreater(len(data.get("gemini_prompt", "")), 50)

    def test_updates_check_endpoint(self):
        """Verify /api/updates/check returns current version and update state."""
        res = self.client.get("/api/updates/check")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get("ok"))
        self.assertEqual(data.get("current_version"), VERSION)

    def test_games_emulators_endpoint(self):
        """Verify /api/games/emulators returns emulator detection list."""
        res = self.client.get("/api/games/emulators")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn("emulators", data)
        self.assertIsInstance(data["emulators"], list)

    def test_ai_stack_status_endpoint(self):
        """Verify /api/ai/stack-status reports Ollama, Claude, Node.js readiness."""
        res = self.client.get("/api/ai/stack-status")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn("node", data)
        self.assertIn("claude", data)
        self.assertIn("ollama", data)
        self.assertIn("installed", data["node"])
        self.assertIn("installed", data["claude"])
        self.assertIn("installed", data["ollama"])

    def test_windows_list_endpoint(self):
        """Verify /api/windows/list returns windows array."""
        res = self.client.get("/api/windows/list")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn("windows", data)
        self.assertIsInstance(data["windows"], list)


if __name__ == "__main__":
    unittest.main()
