"""Decide whether a post matches the configured keyword / regex rules."""

from __future__ import annotations

import re
from typing import List

from .config import MatchRules


class Matcher:
    """Compiles MatchRules once and tests text against them repeatedly."""

    def __init__(self, rules: MatchRules):
        self.rules = rules
        flags = 0 if rules.case_sensitive else re.IGNORECASE

        self._keyword_patterns = []
        for kw in rules.keywords:
            if rules.whole_word:
                pattern = r"\b" + re.escape(kw) + r"\b"
            else:
                pattern = re.escape(kw)
            self._keyword_patterns.append((kw, re.compile(pattern, flags)))

        self._regex_patterns = []
        for rx in rules.regexes:
            try:
                self._regex_patterns.append((rx, re.compile(rx, flags)))
            except re.error as exc:
                raise ValueError(f"Invalid regex in config: {rx!r} ({exc})") from exc

    def matches(self, text: str) -> List[str]:
        """Return the list of keyword/regex strings that matched *text*.

        An empty list means no match. The returned labels are exactly the
        keyword or regex strings from the config, so alerts can show them.
        """
        if not text:
            return []
        hits: List[str] = []
        for label, pattern in self._keyword_patterns:
            if pattern.search(text):
                hits.append(label)
        for label, pattern in self._regex_patterns:
            if pattern.search(text):
                hits.append(f"/{label}/")
        return hits
