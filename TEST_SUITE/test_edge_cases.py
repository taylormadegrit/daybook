"""
Edge case tests for Daybook:
- Unicode, multilingual text, and emojis across notes and reminders
- Extremely large text payloads (stress testing note storage)
- Boundary date/time calculations (leap year, year boundary, midnight)
- Out-of-bounds IDs and malformed request formats
"""
import unittest
import json
from datetime import datetime
from reminders.web import app
from reminders import db, nlp


class TestEdgeCases(unittest.TestCase):
    """Edge case and boundary condition test suite."""

    @classmethod
    def setUpClass(cls):
        app.config["TESTING"] = True
        cls.client = app.test_client()

    def test_unicode_and_emojis_in_notes(self):
        """Verify notes handle full Unicode, Asian CJK glyphs, and emojis without corruption."""
        title = "🚀 Test Title 漢字 · العربية · 日本語 🌟"
        body = "Emoji test 🎉🔥 with Unicode text: こんにちは, مرحبا, 你好, Привет."
        res = self.client.post("/api/notes",
                               data=json.dumps({"title": title, "body": body, "category": "Personal"}),
                               content_type="application/json")
        self.assertIn(res.status_code, [200, 201])
        data = res.get_json()
        nid = data.get("id") or (data.get("note") or {}).get("id")

        # Fetch and verify encoding fidelity
        get_res = self.client.get(f"/api/notes/{nid}")
        self.assertEqual(get_res.status_code, 200)
        note = get_res.get_json()
        self.assertEqual(note.get("title"), title)
        self.assertEqual(note.get("body"), body)

        # Cleanup
        self.client.delete(f"/api/notes/{nid}")

    def test_large_note_payload(self):
        """Stress test with 100,000 characters payload."""
        large_body = "A" * 100000
        res = self.client.post("/api/notes",
                               data=json.dumps({"title": "Large Payload Test", "body": large_body}),
                               content_type="application/json")
        self.assertIn(res.status_code, [200, 201])
        data = res.get_json()
        nid = data.get("id") or (data.get("note") or {}).get("id")

        get_res = self.client.get(f"/api/notes/{nid}")
        self.assertEqual(get_res.status_code, 200)
        note = get_res.get_json()
        self.assertEqual(len(note.get("body", "")), 100000)

        # Cleanup
        self.client.delete(f"/api/notes/{nid}")

    def test_nonexistent_and_invalid_ids(self):
        """Verify 404 or clean error handling on negative and non-existent IDs."""
        res_note = self.client.get("/api/notes/999999999")
        self.assertIn(res_note.status_code, [404, 200])  # If 200, must be null or error dict
        if res_note.status_code == 200:
            self.assertIsNone(res_note.get_json())

        res_rem = self.client.post("/api/reminders/999999999/done")
        self.assertIn(res_rem.status_code, [200, 404])

    def test_empty_string_search(self):
        """Verify empty string or whitespace search does not crash."""
        res = self.client.get("/api/notes?q=")
        self.assertEqual(res.status_code, 200)
        self.assertIsInstance(res.get_json(), list)

        res_spaces = self.client.get("/api/notes?q=%20%20%20")
        self.assertEqual(res_spaces.status_code, 200)
        self.assertIsInstance(res_spaces.get_json(), list)

    def test_date_boundary_leap_year(self):
        """Verify handling of leap year boundaries in next_occurrence."""
        leap_day = datetime(2028, 2, 29, 12, 0, 0)
        next_day = db.next_occurrence(leap_day, "daily", now=leap_day)
        self.assertEqual(next_day.month, 3)
        self.assertEqual(next_day.day, 1)

        # Test yearly repeat on leap day
        next_year = db.next_occurrence(leap_day, "yearly", now=leap_day)
        self.assertEqual(next_year.year, 2029)
        self.assertEqual(next_year.month, 2)
        self.assertEqual(next_year.day, 28)  # non-leap year clamps to Feb 28

    def test_special_characters_in_search(self):
        """Verify SQL characters and wildcards (% and _) don't break search."""
        for pattern in ["%", "_", "'", "\"", "\\", ";", "--", "/*"]:
            res = self.client.get(f"/api/notes?q={pattern}")
            self.assertEqual(res.status_code, 200, f"Search failed for pattern: {pattern}")


if __name__ == "__main__":
    unittest.main()
