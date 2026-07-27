"""Persist the set of already-seen post ids so we never alert twice.

State is a small JSON file mapping each source name to a list of seen post ids.
The list is capped per source so it can't grow without bound.
"""

from __future__ import annotations

import json
import os
import tempfile
from typing import Dict, List

MAX_IDS_PER_SOURCE = 500


class State:
    def __init__(self, path: str):
        self.path = path
        self._seen: Dict[str, List[str]] = {}
        self._seen_sets: Dict[str, set] = {}
        self._load()

    def _load(self) -> None:
        if not os.path.exists(self.path):
            return
        try:
            with open(self.path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except (json.JSONDecodeError, OSError):
            # Corrupt or unreadable state: start fresh rather than crash.
            data = {}
        seen = data.get("seen", {}) if isinstance(data, dict) else {}
        for source, ids in seen.items():
            if isinstance(ids, list):
                self._seen[source] = [str(i) for i in ids]
                self._seen_sets[source] = set(self._seen[source])

    def has_source(self, source: str) -> bool:
        """True if we have ever recorded state for this source before."""
        return source in self._seen

    def is_seen(self, source: str, post_id: str) -> bool:
        return post_id in self._seen_sets.get(source, set())

    def mark_seen(self, source: str, post_id: str) -> None:
        if source not in self._seen:
            self._seen[source] = []
            self._seen_sets[source] = set()
        if post_id in self._seen_sets[source]:
            return
        self._seen[source].append(post_id)
        self._seen_sets[source].add(post_id)
        # Trim oldest ids beyond the cap.
        overflow = len(self._seen[source]) - MAX_IDS_PER_SOURCE
        if overflow > 0:
            dropped = self._seen[source][:overflow]
            self._seen[source] = self._seen[source][overflow:]
            for d in dropped:
                self._seen_sets[source].discard(d)

    def save(self) -> None:
        """Atomically write state to disk."""
        payload = {"seen": self._seen}
        directory = os.path.dirname(os.path.abspath(self.path))
        os.makedirs(directory, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=directory, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, indent=2)
            os.replace(tmp, self.path)
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)
