import unittest

from monitor.feeds import FeedError, parse

RSS = """<?xml version="1.0"?>
<rss version="2.0">
  <channel>
    <title>Example Page</title>
    <item>
      <title>Grand Opening!</title>
      <link>https://facebook.com/post/1</link>
      <guid>post-1</guid>
      <description>Come to our &lt;b&gt;grand opening&lt;/b&gt; sale.</description>
      <pubDate>Mon, 27 Jul 2026 10:00:00 GMT</pubDate>
    </item>
    <item>
      <title>Second post</title>
      <link>https://facebook.com/post/2</link>
      <guid>post-2</guid>
      <description>Nothing special.</description>
    </item>
  </channel>
</rss>
"""

ATOM = """<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Example</title>
  <entry>
    <title>Hiring now</title>
    <id>urn:uuid:abc</id>
    <link rel="alternate" href="https://facebook.com/post/a"/>
    <updated>2026-07-27T10:00:00Z</updated>
    <summary>We are &lt;i&gt;hiring&lt;/i&gt;.</summary>
  </entry>
</feed>
"""

JSON_FEED = """
{
  "version": "https://jsonfeed.org/version/1",
  "title": "Example",
  "items": [
    {
      "id": "json-1",
      "url": "https://facebook.com/post/j1",
      "title": "Big sale",
      "content_html": "<p>Everything <b>50% off</b></p>",
      "date_published": "2026-07-27T10:00:00Z"
    }
  ]
}
"""


class ParseRssTest(unittest.TestCase):
    def test_parses_items(self):
        posts = parse(RSS)
        self.assertEqual(len(posts), 2)
        self.assertEqual(posts[0].id, "post-1")
        self.assertEqual(posts[0].title, "Grand Opening!")
        # HTML is stripped and entities decoded.
        self.assertIn("grand opening", posts[0].body)
        self.assertNotIn("<b>", posts[0].body)
        self.assertEqual(posts[0].url, "https://facebook.com/post/1")

    def test_searchable_text(self):
        posts = parse(RSS)
        self.assertIn("Grand Opening", posts[0].searchable_text)
        self.assertIn("sale", posts[0].searchable_text)


class ParseAtomTest(unittest.TestCase):
    def test_parses_entry(self):
        posts = parse(ATOM)
        self.assertEqual(len(posts), 1)
        self.assertEqual(posts[0].id, "urn:uuid:abc")
        self.assertEqual(posts[0].url, "https://facebook.com/post/a")
        self.assertIn("hiring", posts[0].body)


class ParseJsonFeedTest(unittest.TestCase):
    def test_parses_items(self):
        posts = parse(JSON_FEED)
        self.assertEqual(len(posts), 1)
        self.assertEqual(posts[0].id, "json-1")
        self.assertIn("50% off", posts[0].body)
        self.assertNotIn("<b>", posts[0].body)


class ParseErrorsTest(unittest.TestCase):
    def test_empty(self):
        with self.assertRaises(FeedError):
            parse("   ")

    def test_garbage(self):
        with self.assertRaises(FeedError):
            parse("not a feed at all")

    def test_bad_json(self):
        with self.assertRaises(FeedError):
            parse("{ broken json ")


if __name__ == "__main__":
    unittest.main()
