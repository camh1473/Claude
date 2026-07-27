"""Send alerts to Slack via an incoming webhook."""

from __future__ import annotations

from typing import List, Optional

import requests

from .config import SlackConfig
from .feeds import Post

REQUEST_TIMEOUT = 15


class NotifyError(Exception):
    """Raised when an alert could not be delivered."""


def _excerpt(text: str, limit: int = 500) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def build_slack_payload(
    source_name: str, post: Post, matched: List[str], slack: SlackConfig
) -> dict:
    """Build the JSON payload for a Slack incoming webhook."""
    keywords = ", ".join(f"`{m}`" for m in matched)
    body = _excerpt(post.body or post.title)

    header = f":mega: Keyword match on *{source_name}*"
    fields = [f"*Matched:* {keywords}"]
    if post.title:
        fields.append(f"*Post:* {post.title}")
    if post.published:
        fields.append(f"*Published:* {post.published}")

    blocks = [
        {"type": "section", "text": {"type": "mrkdwn", "text": header}},
        {"type": "section", "text": {"type": "mrkdwn", "text": "\n".join(fields)}},
    ]
    if body:
        blocks.append(
            {"type": "section", "text": {"type": "mrkdwn", "text": _excerpt(body)}}
        )
    if post.url:
        blocks.append(
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"<{post.url}|View post ↗>"},
            }
        )

    # `text` is a plain-text fallback for notifications and clients that don't
    # render blocks.
    fallback = f"[{source_name}] matched {', '.join(matched)}: {post.title or body}"
    payload = {"text": fallback, "blocks": blocks}
    if slack.username:
        payload["username"] = slack.username
    if slack.icon_emoji:
        payload["icon_emoji"] = slack.icon_emoji
    return payload


def send_slack(
    payload: dict, webhook_url: str, *, session: Optional[requests.Session] = None
) -> None:
    """POST *payload* to the Slack webhook. Raises NotifyError on failure."""
    if not webhook_url:
        raise NotifyError(
            "No Slack webhook configured. Set SLACK_WEBHOOK_URL or slack.webhook_url."
        )
    sess = session or requests
    try:
        resp = sess.post(webhook_url, json=payload, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise NotifyError(f"Slack delivery failed: {exc}") from exc
