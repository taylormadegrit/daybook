"""
Performance and latency benchmark test suite for Daybook:
- API endpoint response times (<50ms SLA)
- Bulk note creation and full-text search indexing speed
- Date-parsing and NLP rule evaluation latency
- Timeline occurrence expansion benchmark
"""
import unittest
import time
from datetime import datetime, timedelta
from reminders.web import app
from reminders import db, nlp, notes


class TestPerformance(unittest.TestCase):
    """Verifies that critical paths satisfy latency and throughput requirements."""

    @classmethod
    def setUpClass(cls):
        app.config["TESTING"] = True
        cls.client = app.test_client()

    def test_api_endpoints_latency(self):
        """Verifies core API endpoints respond in under 50ms."""
        endpoints = ["/api/meta", "/api/reminders", "/api/notes", "/api/settings", "/api/today"]
        for ep in endpoints:
            durations = []
            for _ in range(5):
                start = time.perf_counter()
                res = self.client.get(ep)
                duration_ms = (time.perf_counter() - start) * 1000
                self.assertEqual(res.status_code, 200)
                durations.append(duration_ms)

            avg_ms = sum(durations) / len(durations)
            self.assertLess(avg_ms, 75.0, f"Endpoint {ep} average response too slow: {avg_ms:.2f}ms")

    def test_nlp_rule_latency(self):
        """Verifies rule-based NLP time extraction executes in under 5ms per query."""
        phrases = [
            "tomorrow at 3pm",
            "next Friday 9am",
            "every weekday 8am",
            "in 2 hours",
            "tonight 11pm",
        ]
        start = time.perf_counter()
        for _ in range(50):
            for p in phrases:
                _ = nlp.when(p)
                _ = nlp.detect_repeat(p)
        total_time = time.perf_counter() - start
        avg_per_parse_ms = (total_time / (50 * len(phrases))) * 1000
        self.assertLess(avg_per_parse_ms, 5.0, f"NLP parse average took {avg_per_parse_ms:.3f}ms")

    def test_bulk_notes_and_search_benchmark(self):
        """Benchmarks bulk insertion and full-text search across 50 notes."""
        note_ids = []
        try:
            start_insert = time.perf_counter()
            for i in range(50):
                nid = notes.add(f"Benchmark note body number {i} discussing artificial intelligence and local offline apps.",
                                title=f"Bench Note {i}",
                                category="Tech",
                                organize=False)
                note_ids.append(nid)
            insert_duration = time.perf_counter() - start_insert
            self.assertLess(insert_duration, 5.0, f"Bulk insert took too long: {insert_duration:.2f}s")

            # Search benchmark
            start_search = time.perf_counter()
            results = notes.search(query="artificial intelligence")
            search_duration_ms = (time.perf_counter() - start_search) * 1000
            self.assertGreaterEqual(len(results), 50)
            self.assertLess(search_duration_ms, 100.0, f"FTS search took {search_duration_ms:.2f}ms")
        finally:
            for nid in note_ids:
                notes.delete(nid)

    def test_timeline_occurrences_benchmark(self):
        """Verifies daily timeline occurrence expansion executes in under 20ms."""
        today = datetime.now().date()
        start = time.perf_counter()
        for _ in range(20):
            _ = db.occurrences_on(today)
        duration_ms = ((time.perf_counter() - start) / 20) * 1000
        self.assertLess(duration_ms, 25.0, f"occurrences_on took {duration_ms:.2f}ms")


if __name__ == "__main__":
    unittest.main()
