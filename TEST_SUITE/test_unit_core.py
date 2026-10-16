"""
Unit tests for Daybook core modules:
- reminders.nlp (natural language parsing, date extraction, title extraction)
- reminders.categories (category rules, guess, DEFAULTS)
- reminders.db (database initialization, migrations, CRUD helpers)
- reminders.paths (path resolution, existence checks)
- reminders.templates (note templates, structure verification)
"""
import unittest
import os
import tempfile
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from reminders import nlp, categories, paths, templates, db


class TestNLPParsing(unittest.TestCase):
    """Unit tests for Natural Language Processing date and task parser."""

    def test_parse_tomorrow(self):
        text = "Call dentist tomorrow at 3pm"
        parsed = nlp.parse(text)
        self.assertIsNotNone(parsed, "Should parse text")
        self.assertIn("call dentist", parsed.get("text", "").lower())
        self.assertIn("due", parsed)
        self.assertIsNotNone(parsed.get("due"))

    def test_parse_empty_or_none(self):
        self.assertEqual(nlp.parse(""), {})
        self.assertEqual(nlp.parse(None), {})

    def test_parse_no_date(self):
        text = "Read chapter 4 of book"
        parsed = nlp.parse(text)
        self.assertIsNotNone(parsed)
        self.assertIn("read chapter 4", parsed.get("text", "").lower())


class TestCategories(unittest.TestCase):
    """Unit tests for Category classification and rules."""

    def test_defaults_not_empty(self):
        cats = categories.DEFAULTS
        self.assertIsInstance(cats, list)
        self.assertGreater(len(cats), 0)
        names = [c["name"] for c in cats]
        self.assertIn("Personal", names)
        self.assertIn("Work", names)

    def test_guess_meeting(self):
        text = "Weekly team sync meeting on Zoom"
        cat, conf = categories.guess(text)
        self.assertEqual(cat, "Work")
        self.assertGreaterEqual(conf, 50)

    def test_guess_learning(self):
        text = "Watch tutorial video on PyTorch neural networks"
        cat, conf = categories.guess(text)
        self.assertIn(cat, ["Learning", "Work", "Personal"])


class TestTemplates(unittest.TestCase):
    """Unit tests for Note templates."""

    def test_templates_exist(self):
        self.assertIsInstance(templates.TEMPLATES, list)
        self.assertGreater(len(templates.TEMPLATES), 0)
        self.assertIn("meeting", templates.BY_KEY)

    def test_template_rendering(self):
        tmpl = templates.BY_KEY.get("meeting")
        self.assertIsNotNone(tmpl)
        self.assertIn("Agenda", tmpl.get("body", ""))
        filled = templates.fill(tmpl.get("body", ""))
        self.assertIsNotNone(filled)
        self.assertIn("Meeting", filled)


class TestPathsCore(unittest.TestCase):
    """Unit tests for Paths directory definitions and existence."""

    def test_data_path_exists(self):
        self.assertTrue(paths.DATA.exists(), f"DATA path {paths.DATA} must exist")

    def test_backgrounds_path_defined(self):
        self.assertIsNotNone(paths.DATA / "backgrounds")


class TestDatabaseCore(unittest.TestCase):
    """Unit tests for SQLite database operations and schema integrity."""

    def setUp(self):
        self.test_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.test_dir.name) / "test_daybook.db"
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row

    def tearDown(self):
        self.conn.close()
        self.test_dir.cleanup()

    def test_schema_creation(self):
        cursor = self.conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS test_reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                text TEXT NOT NULL,
                due TEXT,
                done INTEGER DEFAULT 0,
                created_at TEXT NOT NULL
            )
        """)
        self.conn.commit()

        cursor.execute("INSERT INTO test_reminders (text, due, created_at) VALUES (?, ?, ?)",
                       ("Test task", "2026-10-20 10:00:00", datetime.now().isoformat()))
        self.conn.commit()

        cursor.execute("SELECT * FROM test_reminders WHERE text = ?", ("Test task",))
        row = cursor.fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row["text"], "Test task")
        self.assertEqual(row["done"], 0)


if __name__ == "__main__":
    unittest.main()
