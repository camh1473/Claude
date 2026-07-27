import json
import unittest

from monitor.config import SlackConfig
from monitor.feeds import Post
from monitor.notifier import build_slack_payload, format_mentions

POST = Post(
    id="1",
    title="Grand Opening",
    body="Come to our grand opening sale.",
    url="https://facebook.com/post/1",
    published="Mon, 27 Jul 2026 10:00:00 GMT",
)


class FormatMentionsTest(unittest.TestCase):
    def test_user_id(self):
        self.assertEqual(format_mentions(["U01234ABC"]), "<@U01234ABC>")

    def test_leading_at_is_stripped(self):
        self.assertEqual(format_mentions(["@U01234ABC"]), "<@U01234ABC>")

    def test_here_and_channel(self):
        self.assertEqual(format_mentions(["here"]), "<!here>")
        self.assertEqual(format_mentions(["channel"]), "<!channel>")
        self.assertEqual(format_mentions(["everyone"]), "<!channel>")

    def test_already_formatted_passthrough(self):
        self.assertEqual(format_mentions(["<!subteam^S123>"]), "<!subteam^S123>")

    def test_multiple(self):
        self.assertEqual(
            format_mentions(["U1", "U2"]), "<@U1> <@U2>"
        )

    def test_empty(self):
        self.assertEqual(format_mentions([]), "")


class BuildPayloadTest(unittest.TestCase):
    def test_mention_in_header_and_fallback(self):
        slack = SlackConfig(webhook_url="x", mentions=["U01234ABC"])
        payload = build_slack_payload("Test Page", POST, ["grand opening"], slack)
        # Serializes cleanly to JSON.
        json.dumps(payload)
        self.assertIn("<@U01234ABC>", payload["text"])
        header = payload["blocks"][0]["text"]["text"]
        self.assertIn("<@U01234ABC>", header)

    def test_no_mention_when_unset(self):
        slack = SlackConfig(webhook_url="x")
        payload = build_slack_payload("Test Page", POST, ["grand opening"], slack)
        self.assertNotIn("<@", payload["text"])
        self.assertNotIn("<!", payload["blocks"][0]["text"]["text"])

    def test_matched_keywords_shown(self):
        slack = SlackConfig(webhook_url="x")
        payload = build_slack_payload("Test Page", POST, ["grand opening", "sale"], slack)
        blob = json.dumps(payload)
        self.assertIn("grand opening", blob)
        self.assertIn("sale", blob)

    def test_optional_username_and_icon(self):
        slack = SlackConfig(webhook_url="x", username="Monitor", icon_emoji=":mega:")
        payload = build_slack_payload("Test Page", POST, ["sale"], slack)
        self.assertEqual(payload["username"], "Monitor")
        self.assertEqual(payload["icon_emoji"], ":mega:")


if __name__ == "__main__":
    unittest.main()
