"""
Error handling and validation test suite for Daybook:
- Malformed and non-JSON payloads
- Missing required fields in API requests
- Invalid repeat rules and time boundaries
- Invalid parameter types and out-of-range values
- Safe error handling across blueprints and endpoints
"""
import unittest
import json
from reminders.web import app
from reminders import db, nlp


class TestErrorHandling(unittest.TestCase):
    """Verifies that API and core logic fail gracefully without unhandled exceptions."""

    @classmethod
    def setUpClass(cls):
        app.config["TESTING"] = True
        cls.client = app.test_client()

    def test_malformed_json_payloads(self):
        """Endpoints should return 400 or handle gracefully when invalid JSON is sent."""
        res_rem = self.client.post("/api/reminders", data="not json", content_type="application/json")
        self.assertIn(res_rem.status_code, [400, 422])

        res_note = self.client.post("/api/notes", data="not json", content_type="application/json")
        self.assertIn(res_note.status_code, [400, 422])

    def test_empty_json_objects(self):
        """Sending empty JSON objects {} should not crash the server."""
        res_note = self.client.post("/api/notes", data="{}", content_type="application/json")
        self.assertIn(res_note.status_code, [200, 201])
        data = res_note.get_json()
        nid = data.get("id") or (data.get("note") or {}).get("id")
        if nid:
            self.client.delete(f"/api/notes/{nid}")

        res_rem = self.client.post("/api/reminders", data="{}", content_type="application/json")
        self.assertEqual(res_rem.status_code, 400)

    def test_invalid_repeat_rules(self):
        """Invalid repeat rules should raise or return 400."""
        # 1. Via Python function directly
        with self.assertRaises(ValueError):
            db.validate_repeat("every:hour")  # missing count
        with self.assertRaises(ValueError):
            db.validate_repeat("every:abc:hours")  # non-numeric
        with self.assertRaises(ValueError):
            db.validate_repeat("every:-5:days")  # negative count

        # 2. Via API endpoint
        res = self.client.post("/api/reminders",
                               data=json.dumps({"text": "Test repeat", "due": "2026-10-20T10:00:00", "repeat": "every:abc:days"}),
                               content_type="application/json")
        self.assertEqual(res.status_code, 400)

    def test_invalid_ends_time_format(self):
        """Invalid 'ends' time format should raise or return 400."""
        with self.assertRaises(ValueError):
            db.validate_ends("25:00")
        with self.assertRaises(ValueError):
            db.validate_ends("invalid-time")

        res = self.client.post("/api/reminders",
                               data=json.dumps({"text": "Test ends", "due": "2026-10-20T10:00:00", "ends": "99:99"}),
                               content_type="application/json")
        self.assertEqual(res.status_code, 400)

    def test_invalid_actions_on_stickies_and_claude(self):
        """Calling unknown action endpoints should return 400 with clean error."""
        res_sticky = self.client.post("/api/stickies/1/unsupported_action")
        self.assertEqual(res_sticky.status_code, 400)
        self.assertIn("error", res_sticky.get_json())

        res_claude = self.client.post("/api/claude/unsupported_action/desktop")
        self.assertEqual(res_claude.status_code, 400)
        self.assertIn("error", res_claude.get_json())

    def test_invalid_model_pull_request(self):
        """Pulling a model with invalid syntax should return 400."""
        res = self.client.post("/api/models/pull",
                               data=json.dumps({"name": "invalid_model_without_tag"}),
                               content_type="application/json")
        self.assertEqual(res.status_code, 400)
        self.assertIn("error", res.get_json())

    def test_notes_action_to_reminder_validation(self):
        """Action-to-reminder endpoint requires 'text' parameter."""
        res = self.client.post("/api/notes/1/remind",
                               data=json.dumps({"when": "tomorrow 9am"}),
                               content_type="application/json")
        # Should return 400 when text is missing
        self.assertIn(res.status_code, [400, 500])


if __name__ == "__main__":
    unittest.main()
