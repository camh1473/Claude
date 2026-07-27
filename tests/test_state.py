import os
import tempfile
import unittest

from monitor.state import MAX_IDS_PER_SOURCE, State


class StateTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.path = os.path.join(self.dir, "state.json")

    def test_new_source_reports_unseen(self):
        s = State(self.path)
        self.assertFalse(s.has_source("PageA"))
        self.assertFalse(s.is_seen("PageA", "1"))

    def test_mark_and_persist(self):
        s = State(self.path)
        s.mark_seen("PageA", "1")
        s.mark_seen("PageA", "2")
        s.save()

        reloaded = State(self.path)
        self.assertTrue(reloaded.has_source("PageA"))
        self.assertTrue(reloaded.is_seen("PageA", "1"))
        self.assertTrue(reloaded.is_seen("PageA", "2"))
        self.assertFalse(reloaded.is_seen("PageA", "3"))

    def test_idempotent_mark(self):
        s = State(self.path)
        s.mark_seen("PageA", "1")
        s.mark_seen("PageA", "1")
        s.save()
        reloaded = State(self.path)
        self.assertTrue(reloaded.is_seen("PageA", "1"))

    def test_cap_trims_oldest(self):
        s = State(self.path)
        total = MAX_IDS_PER_SOURCE + 50
        for i in range(total):
            s.mark_seen("PageA", str(i))
        # Oldest should have been trimmed, newest retained.
        self.assertFalse(s.is_seen("PageA", "0"))
        self.assertTrue(s.is_seen("PageA", str(total - 1)))

    def test_corrupt_state_starts_fresh(self):
        with open(self.path, "w", encoding="utf-8") as fh:
            fh.write("{ not valid json")
        s = State(self.path)  # should not raise
        self.assertFalse(s.has_source("PageA"))


if __name__ == "__main__":
    unittest.main()
