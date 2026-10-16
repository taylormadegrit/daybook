"""
State and concurrency test suite for Daybook:
- Concurrent multi-threaded database writes and reads
- Rapid reminder completion, snooze, and repeat scheduling
- Concurrent settings updates
- Full-text search concurrency
"""
import unittest
import concurrent.futures
from datetime import datetime, timedelta
from reminders import db, notes


class TestStateConcurrency(unittest.TestCase):
    """Verifies thread safety, state transitions, and concurrency guarantees."""

    def test_concurrent_reminder_writes(self):
        """Verify multiple threads can insert reminders simultaneously without lock contention."""
        created_ids = []

        def worker(i):
            due = datetime.now() + timedelta(hours=i + 1)
            rid = db.add(f"Concurrent Reminder #{i}", due, priority=1, notes=f"Worker {i}")
            return rid

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(worker, i) for i in range(20)]
            for f in concurrent.futures.as_completed(futures):
                rid = f.result()
                self.assertIsNotNone(rid)
                created_ids.append(rid)

        self.assertEqual(len(created_ids), 20)

        # Cleanup
        for rid in created_ids:
            db.delete(rid)

    def test_concurrent_notes_and_fts_search(self):
        """Verify concurrent note creation and FTS indexing without race conditions."""
        note_ids = []

        def writer(i):
            nid = notes.add(f"Body content for note {i} with unique_kw_{i}",
                            title=f"Concurrent Note {i}",
                            category="Tech",
                            organize=False)
            return nid

        def reader(i):
            # Concurrent query
            return notes.search(query="Concurrent")

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            write_futures = [executor.submit(writer, i) for i in range(15)]
            read_futures = [executor.submit(reader, i) for i in range(15)]

            for f in concurrent.futures.as_completed(write_futures):
                nid = f.result()
                self.assertIsNotNone(nid)
                note_ids.append(nid)

            for f in concurrent.futures.as_completed(read_futures):
                res = f.result()
                self.assertIsInstance(res, list)

        self.assertEqual(len(note_ids), 15)

        # Verify search found the concurrent notes
        search_res = notes.search(query="unique_kw_0")
        self.assertGreaterEqual(len(search_res), 1)

        # Cleanup
        for nid in note_ids:
            notes.delete(nid)

    def test_concurrent_settings_updates(self):
        """Verify concurrent updates to different settings do not clobber each other."""
        keys = ["theme", "clock_mode", "startup_view", "snooze_default"]
        values = ["cherry-blossom", "24h", "notes", "15"]

        def update_setting(kv):
            k, v = kv
            db.save_setting(k, v)
            return db.setting(k)

        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(update_setting, pair) for pair in zip(keys, values)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        for k, v in zip(keys, values):
            self.assertEqual(db.setting(k), v)

    def test_repeating_reminder_state_advancement(self):
        """Verify repeating reminders transition state correctly on complete()."""
        now = datetime.now().replace(second=0, microsecond=0)
        due = now - timedelta(hours=2)
        rid = db.add("Daily Checkup", due, repeat="daily")

        # Initial status
        r = db.get(rid)
        self.assertEqual(r["status"], "open")
        self.assertEqual(r["repeat"], "daily")

        # Complete instance -> must advance due time to tomorrow strictly after now
        status = db.complete(rid)
        self.assertTrue(status.startswith("next: "))

        r_after = db.get(rid)
        self.assertEqual(r_after["status"], "open")
        new_due = db.parse_dt(r_after["due"])
        self.assertGreater(new_due, now)

        # Complete non-repeating reminder -> status becomes done
        non_rep_id = db.add("Single Task", due)
        non_rep_status = db.complete(non_rep_id)
        self.assertEqual(non_rep_status, "done")
        self.assertEqual(db.get(non_rep_id)["status"], "done")

        # Cleanup
        db.delete(rid)
        db.delete(non_rep_id)

    def test_rapid_snooze_state(self):
        """Verify rapid snoozing correctly updates due timestamp to latest snooze."""
        rid = db.add("Snooze Target", datetime.now() + timedelta(minutes=5))
        snooze_time_1 = datetime.now().replace(second=0, microsecond=0) + timedelta(minutes=10)
        snooze_time_2 = datetime.now().replace(second=0, microsecond=0) + timedelta(minutes=25)

        db.snooze(rid, snooze_time_1)
        r1 = db.get(rid)
        self.assertEqual(r1["due"], db.fmt(snooze_time_1))

        db.snooze(rid, snooze_time_2)
        r2 = db.get(rid)
        self.assertEqual(r2["due"], db.fmt(snooze_time_2))
        self.assertEqual(r2["status"], "open")

        db.delete(rid)


if __name__ == "__main__":
    unittest.main()
