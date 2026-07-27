"""Fetch and parse feeds into a common Post representation.

Supports RSS 2.0, Atom, and JSON Feed using only the Python standard library
(plus ``requests`` for HTTP), so there are no fragile native dependencies.
"""

from __future__ import annotations

import html
import json
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import List, Optional

import requests

USER_AGENT = "facebook-page-monitor/1.0 (+https://github.com/)"
REQUEST_TIMEOUT = 30

# Namespaces seen in Atom feeds.
_ATOM_NS = "{http://www.w3.org/2005/Atom}"

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


class FeedError(Exception):
    """Raised when a feed cannot be fetched or parsed."""


@dataclass
class Post:
    """A single feed entry, normalized across feed formats."""

    id: str
    title: str
    body: str
    url: str
    published: str = ""

    @property
    def searchable_text(self) -> str:
        """Title + body, used for keyword matching."""
        return f"{self.title}\n{self.body}".strip()


def _strip_html(value: str) -> str:
    """Turn an HTML fragment into readable plain text."""
    if not value:
        return ""
    text = _TAG_RE.sub(" ", value)
    text = html.unescape(text)
    return _WS_RE.sub(" ", text).strip()


def fetch(url: str, *, session: Optional[requests.Session] = None) -> str:
    """Fetch the raw text of a feed. Raises FeedError on HTTP problems."""
    sess = session or requests
    try:
        resp = sess.get(
            url,
            timeout=REQUEST_TIMEOUT,
            headers={"User-Agent": USER_AGENT, "Accept": "application/json, text/xml, */*"},
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise FeedError(f"Failed to fetch feed {url}: {exc}") from exc
    return resp.text


def parse(content: str) -> List[Post]:
    """Parse feed *content* (RSS/Atom/JSON Feed) into a list of Posts.

    Detection is by content sniffing so callers don't need to know the format.
    """
    stripped = content.lstrip()
    if not stripped:
        raise FeedError("Empty feed content.")

    if stripped[0] in "{[":
        return _parse_json_feed(stripped)
    return _parse_xml_feed(stripped)


def _first_nonempty(*values: Optional[str]) -> str:
    for v in values:
        if v:
            return v
    return ""


def _parse_json_feed(content: str) -> List[Post]:
    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        raise FeedError(f"Feed looked like JSON but did not parse: {exc}") from exc

    items = data.get("items") if isinstance(data, dict) else None
    if not isinstance(items, list):
        raise FeedError("JSON Feed has no 'items' array.")

    posts: List[Post] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        title = _first_nonempty(item.get("title"))
        body_html = item.get("content_html") or ""
        body_text = item.get("content_text") or ""
        body = body_text.strip() if body_text else _strip_html(body_html)
        url = _first_nonempty(item.get("url"), item.get("external_url"))
        post_id = _first_nonempty(
            item.get("id"), url, item.get("date_published"), title
        )
        published = _first_nonempty(
            item.get("date_published"), item.get("date_modified")
        )
        if not post_id:
            continue
        posts.append(
            Post(
                id=str(post_id),
                title=_strip_html(title),
                body=body,
                url=url,
                published=published,
            )
        )
    return posts


def _text(elem: Optional[ET.Element]) -> str:
    if elem is None:
        return ""
    return (elem.text or "").strip()


def _parse_xml_feed(content: str) -> List[Post]:
    try:
        root = ET.fromstring(content)
    except ET.ParseError as exc:
        raise FeedError(f"Could not parse feed as XML: {exc}") from exc

    tag = root.tag.lower()
    # RSS 2.0 / RDF: <rss><channel><item>...  or channel is the root.
    if tag.endswith("rss") or tag.endswith("rdf"):
        channel = root.find("channel")
        items = channel.findall("item") if channel is not None else root.findall("item")
        return [_rss_item_to_post(it) for it in items]
    if tag.endswith("channel"):
        return [_rss_item_to_post(it) for it in root.findall("item")]
    # Atom: <feed><entry>...
    if tag.endswith("feed"):
        return [_atom_entry_to_post(e) for e in root.findall(f"{_ATOM_NS}entry")]

    raise FeedError(f"Unrecognized feed root element: <{root.tag}>")


def _rss_item_to_post(item: ET.Element) -> Post:
    title = _text(item.find("title"))
    link = _text(item.find("link"))
    description = _text(item.find("description"))
    # Some feeds use content:encoded for the full body.
    encoded = item.find("{http://purl.org/rss/1.0/modules/content/}encoded")
    body_raw = _text(encoded) or description
    guid = _text(item.find("guid"))
    pub = _text(item.find("pubDate"))
    post_id = _first_nonempty(guid, link, title, pub)
    return Post(
        id=str(post_id),
        title=_strip_html(title),
        body=_strip_html(body_raw),
        url=link,
        published=pub,
    )


def _atom_entry_to_post(entry: ET.Element) -> Post:
    title = _text(entry.find(f"{_ATOM_NS}title"))
    summary = _text(entry.find(f"{_ATOM_NS}summary"))
    content = _text(entry.find(f"{_ATOM_NS}content"))
    body_raw = _first_nonempty(content, summary)
    entry_id = _text(entry.find(f"{_ATOM_NS}id"))
    updated = _text(entry.find(f"{_ATOM_NS}updated")) or _text(
        entry.find(f"{_ATOM_NS}published")
    )

    # Prefer the alternate link; fall back to the first link with an href.
    link = ""
    for link_el in entry.findall(f"{_ATOM_NS}link"):
        rel = link_el.get("rel", "alternate")
        href = link_el.get("href", "")
        if href and rel == "alternate":
            link = href
            break
        if href and not link:
            link = href

    post_id = _first_nonempty(entry_id, link, title, updated)
    return Post(
        id=str(post_id),
        title=_strip_html(title),
        body=_strip_html(body_raw),
        url=link,
        published=updated,
    )


def fetch_and_parse(url: str, *, session: Optional[requests.Session] = None) -> List[Post]:
    """Convenience: fetch *url* and parse it into Posts."""
    return parse(fetch(url, session=session))
