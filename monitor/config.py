"""Load and validate the monitor's configuration.

The config is YAML. Secrets (the Slack webhook) may be supplied via the
SLACK_WEBHOOK_URL environment variable, which always overrides the file so you
never have to commit a secret.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import List, Optional

try:
    import yaml
except ImportError as exc:  # pragma: no cover - import guard
    raise SystemExit(
        "PyYAML is required. Install dependencies with: pip install -r requirements.txt"
    ) from exc


class ConfigError(Exception):
    """Raised when the configuration is missing or invalid."""


@dataclass
class Source:
    """A single feed to poll (one Facebook page's feed)."""

    name: str
    url: str


@dataclass
class MatchRules:
    """Keyword / regex rules used to decide whether a post is interesting."""

    keywords: List[str] = field(default_factory=list)
    regexes: List[str] = field(default_factory=list)
    case_sensitive: bool = False
    whole_word: bool = False


@dataclass
class SlackConfig:
    webhook_url: str = ""
    username: Optional[str] = None
    icon_emoji: Optional[str] = None
    # Slack user/group ids (or the words "here"/"channel") to @-mention in each
    # alert so it reliably pushes to your phone. May be a single string or list.
    mentions: List[str] = field(default_factory=list)


@dataclass
class Config:
    sources: List[Source]
    match: MatchRules
    slack: SlackConfig
    state_file: str = "state.json"
    poll_interval_seconds: int = 300
    seed_on_first_run: bool = True


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ConfigError(message)


def load_config(path: str) -> Config:
    """Read *path*, validate it, and return a Config.

    Raises ConfigError with a human-readable message on any problem.
    """
    if not os.path.exists(path):
        raise ConfigError(
            f"Config file not found: {path}\n"
            "Copy config.example.yaml to config.yaml and edit it."
        )

    with open(path, "r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}

    _require(isinstance(raw, dict), "Top level of the config must be a mapping.")

    # --- sources ---
    raw_sources = raw.get("sources") or []
    _require(
        isinstance(raw_sources, list) and raw_sources,
        "You must define at least one entry under 'sources'.",
    )
    sources: List[Source] = []
    for i, item in enumerate(raw_sources):
        _require(isinstance(item, dict), f"sources[{i}] must be a mapping.")
        name = item.get("name")
        url = item.get("url")
        _require(bool(name), f"sources[{i}] is missing 'name'.")
        _require(bool(url), f"sources[{i}] ('{name}') is missing 'url'.")
        _require(
            str(url).startswith(("http://", "https://")),
            f"sources[{i}] ('{name}') url must start with http:// or https://.",
        )
        sources.append(Source(name=str(name), url=str(url)))

    # --- match rules ---
    raw_match = raw.get("match") or {}
    _require(isinstance(raw_match, dict), "'match' must be a mapping.")
    keywords = raw_match.get("keywords") or []
    regexes = raw_match.get("regexes") or []
    _require(isinstance(keywords, list), "match.keywords must be a list.")
    _require(isinstance(regexes, list), "match.regexes must be a list.")
    keywords = [str(k) for k in keywords if str(k).strip()]
    regexes = [str(r) for r in regexes if str(r).strip()]
    _require(
        bool(keywords or regexes),
        "Define at least one entry under match.keywords or match.regexes.",
    )
    match = MatchRules(
        keywords=keywords,
        regexes=regexes,
        case_sensitive=bool(raw_match.get("case_sensitive", False)),
        whole_word=bool(raw_match.get("whole_word", False)),
    )

    # --- slack ---
    raw_slack = raw.get("slack") or {}
    _require(isinstance(raw_slack, dict), "'slack' must be a mapping.")
    webhook = os.environ.get("SLACK_WEBHOOK_URL") or raw_slack.get("webhook_url") or ""

    # `mention` may be a single string or a list; env var SLACK_MENTION overrides.
    raw_mention = os.environ.get("SLACK_MENTION", raw_slack.get("mention"))
    if raw_mention is None:
        mentions: List[str] = []
    elif isinstance(raw_mention, list):
        mentions = [str(m).strip() for m in raw_mention if str(m).strip()]
    else:
        # Allow a comma/space-separated string too (handy for the env var).
        mentions = [m.strip() for m in re.split(r"[,\s]+", str(raw_mention)) if m.strip()]

    slack = SlackConfig(
        webhook_url=str(webhook).strip(),
        username=raw_slack.get("username"),
        icon_emoji=raw_slack.get("icon_emoji"),
        mentions=mentions,
    )

    # --- misc ---
    poll_interval = raw.get("poll_interval_seconds", 300)
    _require(
        isinstance(poll_interval, int) and poll_interval > 0,
        "poll_interval_seconds must be a positive integer.",
    )

    return Config(
        sources=sources,
        match=match,
        slack=slack,
        state_file=str(raw.get("state_file", "state.json")),
        poll_interval_seconds=poll_interval,
        seed_on_first_run=bool(raw.get("seed_on_first_run", True)),
    )
