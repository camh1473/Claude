"""Run one polling cycle: fetch feeds, match, alert, persist state."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import requests

from .config import Config
from .feeds import FeedError, fetch_and_parse
from .matcher import Matcher
from .notifier import NotifyError, build_slack_payload, send_slack
from .state import State

log = logging.getLogger("monitor")


@dataclass
class CycleStats:
    sources_ok: int = 0
    sources_failed: int = 0
    new_posts: int = 0
    matches: int = 0
    alerts_sent: int = 0
    alerts_failed: int = 0
    seeded: int = 0


def run_cycle(config: Config, *, dry_run: bool = False) -> CycleStats:
    """Poll every source once and return statistics for the cycle."""
    stats = CycleStats()
    matcher = Matcher(config.match)
    state = State(config.state_file)
    session = requests.Session()

    for source in config.sources:
        first_time = not state.has_source(source.name)
        seeding = first_time and config.seed_on_first_run

        try:
            posts = fetch_and_parse(source.url, session=session)
        except FeedError as exc:
            stats.sources_failed += 1
            log.error("[%s] %s", source.name, exc)
            continue

        stats.sources_ok += 1
        log.info("[%s] fetched %d post(s)", source.name, len(posts))

        if seeding:
            for post in posts:
                state.mark_seen(source.name, post.id)
            stats.seeded += len(posts)
            log.info(
                "[%s] first run: recorded %d existing post(s) without alerting",
                source.name,
                len(posts),
            )
            continue

        # Process oldest first so alert order matches posting order.
        for post in reversed(posts):
            if state.is_seen(source.name, post.id):
                continue
            stats.new_posts += 1
            matched = matcher.matches(post.searchable_text)
            if matched:
                stats.matches += 1
                _handle_match(source.name, post, matched, config, session, dry_run, stats)
            # Mark seen whether or not it matched, so we evaluate each post once.
            state.mark_seen(source.name, post.id)

    if not dry_run:
        state.save()
    else:
        log.info("dry-run: state not saved")

    return stats


def _handle_match(source_name, post, matched, config, session, dry_run, stats) -> None:
    label = ", ".join(matched)
    if dry_run:
        log.info("[%s] MATCH (%s): %s", source_name, label, post.title or post.url)
        return
    payload = build_slack_payload(source_name, post, matched, config.slack)
    try:
        send_slack(payload, config.slack.webhook_url, session=session)
        stats.alerts_sent += 1
        log.info("[%s] alert sent (%s): %s", source_name, label, post.title or post.url)
    except NotifyError as exc:
        stats.alerts_failed += 1
        log.error("[%s] %s", source_name, exc)
