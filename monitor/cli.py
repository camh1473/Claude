"""Command-line entry point for the Facebook Page Monitor."""

from __future__ import annotations

import argparse
import logging
import sys
import time

from .config import ConfigError, load_config
from .core import run_cycle


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="facebook-page-monitor",
        description="Monitor public Facebook page feeds for keywords and alert to Slack.",
    )
    parser.add_argument(
        "--config", "-c", default="config.yaml", help="Path to config file (default: config.yaml)."
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--once", action="store_true", help="Run a single polling cycle and exit (best for cron)."
    )
    mode.add_argument(
        "--loop", action="store_true", help="Run continuously, polling on the configured interval."
    )
    mode.add_argument(
        "--test-alert",
        action="store_true",
        help="Send one sample alert to Slack (tests your webhook + mention + phone push), then exit.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Match and log, but do not send Slack alerts or save state.",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable debug-level logging."
    )
    return parser


def _configure_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def main(argv=None) -> int:
    args = _build_parser().parse_args(argv)
    _configure_logging(args.verbose)
    log = logging.getLogger("monitor")

    try:
        config = load_config(args.config)
    except ConfigError as exc:
        log.error("Configuration error: %s", exc)
        return 2

    if args.test_alert:
        return _send_test_alert(config, log)

    if not args.loop:
        # Default and --once both mean "one cycle".
        stats = run_cycle(config, dry_run=args.dry_run)
        _log_summary(log, stats)
        return 0

    log.info(
        "Starting loop: polling %d source(s) every %d seconds. Ctrl-C to stop.",
        len(config.sources),
        config.poll_interval_seconds,
    )
    try:
        while True:
            stats = run_cycle(config, dry_run=args.dry_run)
            _log_summary(log, stats)
            time.sleep(config.poll_interval_seconds)
    except KeyboardInterrupt:
        log.info("Stopped.")
        return 0


def _send_test_alert(config, log) -> int:
    """Send one sample alert to Slack to verify webhook + mention + phone push."""
    from .feeds import Post
    from .notifier import NotifyError, build_slack_payload, send_slack

    post = Post(
        id="test-alert",
        title="Test alert from Facebook Page Monitor",
        body=(
            "If this reached your phone, your Slack webhook and mention are "
            "working. You can delete this message."
        ),
        url="https://github.com/",
        published="just now",
    )
    payload = build_slack_payload(
        "Facebook Page Monitor (test)", post, ["test-keyword"], config.slack
    )
    try:
        send_slack(payload, config.slack.webhook_url)
    except NotifyError as exc:
        log.error("%s", exc)
        return 1
    mention_note = (
        f" (mentioning {', '.join(config.slack.mentions)})"
        if config.slack.mentions
        else " (no mention configured)"
    )
    log.info("Test alert sent to Slack%s. Check Slack and your phone.", mention_note)
    return 0


def _log_summary(log, stats) -> None:
    log.info(
        "cycle done: sources ok=%d failed=%d | new posts=%d matches=%d "
        "alerts sent=%d failed=%d seeded=%d",
        stats.sources_ok,
        stats.sources_failed,
        stats.new_posts,
        stats.matches,
        stats.alerts_sent,
        stats.alerts_failed,
        stats.seeded,
    )


if __name__ == "__main__":
    sys.exit(main())
