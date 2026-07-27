import unittest

from monitor.config import MatchRules
from monitor.matcher import Matcher


class MatcherTest(unittest.TestCase):
    def test_case_insensitive_substring(self):
        m = Matcher(MatchRules(keywords=["Sale"]))
        self.assertEqual(m.matches("Big SALE today"), ["Sale"])

    def test_case_sensitive(self):
        m = Matcher(MatchRules(keywords=["Sale"], case_sensitive=True))
        self.assertEqual(m.matches("big sale today"), [])
        self.assertEqual(m.matches("big Sale today"), ["Sale"])

    def test_whole_word(self):
        m = Matcher(MatchRules(keywords=["sale"], whole_word=True))
        self.assertEqual(m.matches("wholesale prices"), [])
        self.assertEqual(m.matches("a sale here"), ["sale"])

    def test_substring_without_whole_word(self):
        m = Matcher(MatchRules(keywords=["sale"], whole_word=False))
        self.assertEqual(m.matches("wholesale prices"), ["sale"])

    def test_regex(self):
        m = Matcher(MatchRules(regexes=[r"\d+% off"]))
        self.assertEqual(m.matches("now 25% off"), ["/\\d+% off/"])

    def test_multiple_hits(self):
        m = Matcher(MatchRules(keywords=["hiring", "grand opening"]))
        hits = m.matches("Grand Opening and now hiring!")
        self.assertIn("hiring", hits)
        self.assertIn("grand opening", hits)

    def test_no_match(self):
        m = Matcher(MatchRules(keywords=["nope"]))
        self.assertEqual(m.matches("nothing here"), [])

    def test_empty_text(self):
        m = Matcher(MatchRules(keywords=["x"]))
        self.assertEqual(m.matches(""), [])

    def test_invalid_regex_raises(self):
        with self.assertRaises(ValueError):
            Matcher(MatchRules(regexes=["(unclosed"]))


if __name__ == "__main__":
    unittest.main()
