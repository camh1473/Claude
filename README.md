# Facebook Page Monitor

A lightweight, no-browser bot that watches one or more **public Facebook pages**
for keywords and sends you a **Slack** alert whenever a new post matches.

It does **not** scrape Facebook directly and does **not** drive a browser.
Instead it polls a **feed** (RSS / Atom / JSON Feed) over plain HTTP, matches
your keywords, remembers what it has already seen, and posts matches to Slack.
It runs fine from a laptop, a cron job, a small VPS, or a scheduled CI job.

---

## Why a feed instead of the Facebook API?

Meta's official **Graph API only returns post content for Pages you manage**
(where you're an admin and can mint a Page access token). Reading an arbitrary
**public** page you don't own was removed for general developer apps after 2018.

So to monitor a page you *don't* control, without a browser, the clean approach
is to put a small **feed service in the middle**:

1. A service such as **[RSS.app](https://rss.app)** (or any equivalent) turns a
   public Facebook page URL into an RSS or JSON feed. It handles the messy
   Facebook side and the terms-of-service relationship.
2. **This bot** just polls that feed URL — no Facebook credentials, no browser.

Because the bot is **source-agnostic**, the same code works with:

- an RSS.app feed (recommended for pages you don't own),
- any other RSS/Atom/JSON-Feed provider,
- or a feed you generate yourself from the Graph API if you *do* get page access
  later.

> **Note on terms of service:** monitoring public information is generally fine,
> but you are responsible for complying with Facebook's and your feed provider's
> terms. This tool deliberately avoids scraping/automating Facebook itself so
> that responsibility stays with the feed provider you choose.

---

## Setup

### 1. Install

```bash
git clone <this-repo>
cd <this-repo>
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

Requires Python 3.9+. The only third-party dependency is `requests`.

### 2. Create a feed for the page(s) you want to watch

Using RSS.app (free tier available) as an example:

1. Sign in at <https://rss.app>.
2. Paste the public Facebook page URL (e.g.
   `https://www.facebook.com/SomePublicPage`) and generate a feed.
3. Copy the feed URL it gives you (an `...xml` RSS feed or a JSON Feed URL).

Repeat for each page you want to monitor. Any provider that outputs RSS, Atom,
or JSON Feed will work.

### 3. Create a Slack incoming webhook

1. Go to <https://api.slack.com/apps> → **Create New App** → *From scratch*.
2. Enable **Incoming Webhooks**, then **Add New Webhook to Workspace** and pick
   the channel you want alerts in.
3. Copy the webhook URL (looks like
   `https://hooks.slack.com/services/T000/B000/XXXX`).

### 4. Configure

```bash
cp config.example.yaml config.yaml
```

Edit `config.yaml`: add your feed URL(s) under `sources`, your keywords under
`match`, and your Slack webhook. **Prefer** putting the webhook in an
environment variable instead of the file:

```bash
export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/..."
```

The env var wins over anything in the config file, so you never have to commit a
secret.

### 5. Run

Check your setup without sending anything to Slack:

```bash
python run.py --config config.yaml --once --dry-run
```

Do one polling cycle (ideal for cron):

```bash
python run.py --config config.yaml --once
```

Run continuously, polling on the configured interval:

```bash
python run.py --config config.yaml --loop
```

---

## How matching works

For every **new** post in a feed (posts already seen are skipped), the bot
checks the post's title + body against your rules:

- `keywords`: plain text matches (case-insensitive by default).
- `regexes`: full Python regular expressions for advanced patterns.
- `whole_word: true` makes plain keywords match only on word boundaries, so
  `sale` won't fire on `wholesale`.

A post triggers **one** Slack alert listing exactly which keywords/patterns
matched. See `config.example.yaml` for all options.

### Getting alerts to buzz your phone

Set `slack.mention` so each alert @-mentions you — a mention fires a push
notification even if the channel is muted, which is the most reliable way to get
an immediate phone buzz:

```yaml
slack:
  mention: "U01234ABC"        # your Slack member id
  # mention: "here"           # or notify everyone currently in the channel
  # mention: ["U01234ABC", "U05678XYZ"]   # or a list of people
```

Find your member id in Slack: **Profile → ⋯ (More) → Copy member ID**. You can
also set it via the `SLACK_MENTION` environment variable, which overrides the
config file. Then make sure notifications for that channel are enabled in the
Slack mobile app.

### First run doesn't flood you

The first time the bot sees a brand-new feed (no saved state yet), it records
the current posts as "already seen" **without** alerting, so you don't get a
burst of alerts for old posts. New posts after that trigger alerts normally.
Disable this with `seed_on_first_run: false` if you *want* to be alerted on the
existing backlog.

---

## Scheduling

**cron** (every 10 minutes):

```cron
*/10 * * * * cd /path/to/repo && /path/to/.venv/bin/python run.py --config config.yaml --once >> monitor.log 2>&1
```

Use `--once` for cron/CI (the scheduler provides the repetition) and `--loop`
only for a long-running process. Keep `state.json` on persistent storage so the
bot remembers what it has seen between runs.

### GitHub Actions (free, no server of your own)

A ready-to-use workflow is included at `.github/workflows/monitor.yml`. It runs
the bot on a schedule and persists `state.json` between runs using the Actions
cache, so the bot remembers what it has already alerted on.

Setup:

1. **Add the Slack webhook as a repository secret.** In your repo on GitHub go
   to **Settings → Secrets and variables → Actions → New repository secret**,
   name it `SLACK_WEBHOOK_URL`, and paste your webhook URL. It is never stored
   in the repo.
2. **Edit `config.ci.yaml`** (this one *is* committed — feed URLs and keywords
   aren't secrets) with your feed URL(s) and keywords, then commit and push.
3. **Enable Actions** for the repo if it isn't already (Actions tab), and adjust
   the `cron:` schedule in the workflow to taste.

Notes:

- The workflow uses `--once`; GitHub's cron provides the repetition (5-minute
  minimum, and scheduled runs are frequently delayed under load — don't expect
  to-the-minute timing).
- State is cached with a rolling key. If the cache is ever evicted (GitHub
  removes caches untouched for 7 days, or over the 10 GB repo limit), the next
  run looks like a first run and silently re-seeds — you'd miss alerts for that
  one gap, then resume normally.
- The very first run seeds silently (no alerts for the existing backlog); new
  posts after that trigger alerts.

### Other serverless / cron hosts

Run with `--once` on a schedule and persist `state.json` between runs (a small
volume, object store, or the platform's cache), otherwise every run looks like a
"first run".

---

## Project layout

```
run.py                  Thin entry point → monitor.cli
config.example.yaml     Copy to config.yaml and edit
requirements.txt        Single dependency: requests
monitor/
  config.py             Load + validate config, env overrides
  feeds.py              Fetch + parse RSS / Atom / JSON Feed → Post objects
  matcher.py            Keyword / regex / whole-word matching
  state.py              Persist "already seen" post ids (JSON)
  notifier.py           Slack incoming-webhook sender
  core.py               One polling cycle, wiring it all together
  cli.py                Argument parsing and run/loop control
tests/                  Offline unit tests (no network needed)
```

## Testing

Test in layers, cheapest first — each step proves one more piece of the chain.

### 1. Code sanity (no accounts needed)

```bash
python -m unittest discover -s tests -v
```

Runs fully offline; covers feed parsing, keyword matching, state persistence,
and Slack payload/mention building.

### 2. Prove Slack → your phone (isolates the alert half)

Create the Slack webhook (see *Setup*), put it and your `mention` in
`config.yaml` (or export `SLACK_WEBHOOK_URL` / `SLACK_MENTION`), then:

```bash
python run.py --config config.yaml --test-alert
```

This sends one sample alert and exits. You should see it in the Slack channel
**and** get a push on your phone within a few seconds. If the message shows up
in Slack but your phone stays quiet, the problem is phone-side: check the Slack
mobile app's notification settings for that channel, and confirm your `mention`
is your real member ID.

### 3. Prove the feed + matching (isolates the Facebook half, sends nothing)

Create a feed (e.g. at RSS.app) for the page and add it under `sources`. Then:

```bash
python run.py --config config.yaml --once --dry-run
```

`--dry-run` fetches the real feed and logs which posts it pulled and which
keywords matched, but sends nothing to Slack and doesn't save state. Tune your
keywords here until the right posts light up. Tip: temporarily set
`seed_on_first_run: false` and add a keyword you know appears in a recent post,
so you can see a real match.

### 4. Prove the whole pipeline

With `seed_on_first_run: false` and a keyword that matches a recent post, run it
for real:

```bash
python run.py --config config.yaml --once
```

A matching post should produce a Slack alert on your phone. Run it a second time
— it should report `new posts=0` (dedup working). Then set `seed_on_first_run`
back to `true` for normal operation.

### 5. Prove the deployment (GitHub Actions)

After following the *GitHub Actions* setup above, go to the repo's **Actions**
tab, pick the **Facebook Page Monitor** workflow, and click **Run workflow**
(that's the `workflow_dispatch` trigger). Watch the run's logs for the
`cycle done: ...` summary, then let the schedule take over.
