# x-thread-getter

Fetch full X.com tweet threads (and X Articles) as clean Markdown + JSON. Free by default using your existing Chrome session; falls back to Grok API for older tweets or edge cases.

**Location:** `~/Code/ubm/x-thread-getter/x-thread-getter.py`
**Invocation:** `x-thread-getter <url>` (symlinked to `~/bin/x-thread-getter`)

---

## Usage

```bash
x-thread-getter "https://x.com/user/status/123"           # save MD + JSON to Obsidian clippings
x-thread-getter "https://x.com/user/status/123" --stdout  # print markdown to stdout
x-thread-getter "https://x.com/user/status/123" --md-only # save markdown only
x-thread-getter "https://x.com/user/status/123" --grok    # force Grok API (paid, ~$0.02)
x-thread-getter "https://x.com/i/article/123456789"       # fetch X Article (Playwright)
x-thread-getter <url> -o /path/to/dir                     # custom output directory
```

## Fetch Methods

### 1. Free (default) — `twitter-api-client` + `browser-cookie3`
- Extracts `auth_token` + `ct0` from Chrome's cookie store via macOS Keychain
- Calls Twitter's internal GraphQL `TweetDetail` endpoint
- **Requires:** Chrome open and logged into X.com
- **Limitation:** Fails on tweets older than ~6 months (GraphQL returns empty)

### 2. X Articles — Playwright
- Detected automatically from `x.com/i/article/<id>` or `x.com/<user>/article/<id>` URLs
- Launches headless Chrome with injected session cookies
- Applies article formatter: strips UI noise, promotes section headings to `##`, adds paragraph spacing
- Embedded articles in threads are also fetched and inlined automatically

### 3. Grok API fallback — `--grok`
- Uses `grok-4` with the `x_search` tool via OpenAI-compatible SDK
- **Cost:** ~$0.02–0.03 per fetch
- Use for: older tweets, rate-limit failures, or when Chrome session is unavailable

## Output Format

Both files saved to `~/Documents/mb Obsidian Vault/Clippings/X.com Clippings/` by default.

**Filename:** `YYYY-MM-DD @handle - slug.md` / `.json`

### Thread Markdown
```markdown
---
source: https://x.com/...
author: "@handle"
fetched: YYYY-MM-DD
tweet_count: N
tags:
  - clipping
  - x-thread
---

---

**Display Name (@handle)** *(Note Tweet)* · 2026-06-02 12:25

Tweet text here...

![](https://pbs.twimg.com/media/....jpg)

---

**Display Name (@handle)** · 2026-06-02 12:26

> *Quoted tweet:*
> **Other Person (@other)**
>
> Quoted tweet text here

---
```

### Article Markdown
```markdown
---
source: https://x.com/i/article/...
author: "@handle"
fetched: YYYY-MM-DD
title: "Article Title"
tags:
  - clipping
  - x-article
---

# Article Title

Intro paragraph...

## Section Heading

Body text...
```

## Features

- **Tweet ordering:** Starts from the focal tweet (the URL you passed), not the start of the conversation thread
- **Timestamps:** Each tweet header shows Sydney local time (AEST)
- **Inline images:** Photos rendered as `![]()` in markdown
- **Quoted tweets:** Extracted inline as blockquotes with their own header
- **Note tweets:** Long-form tweets (>280 chars) fetched in full, flagged *(Note Tweet)*
- **X Article inline embed:** When a thread links to an X Article, it's fetched and embedded automatically
- **Article formatter:** Strips UI noise (byline, engagement counts, footer), promotes headings, adds paragraph spacing

## Dependencies (auto-installed via uv)

- `openai` — Grok API client
- `twitter-api-client` — Twitter internal GraphQL wrapper
- `browser-cookie3` — Chrome cookie extraction with Keychain decryption
- `playwright` — Headless Chrome for X Article fetching

## Known Limitations

- Free method fails on tweets older than ~6 months — use `--grok`
- Rate limiting: for bulk fetches use `--grok` with a manual delay between calls
- Private/locked accounts: untested (Chrome session should work for accounts you follow)
- Very long threads (50+ tweets): pagination untested
- Sydney timezone is hardcoded for timestamps (AEST, UTC+10) — no AEDT adjustment

## Documentation

- **Design history & decisions:** `~/Documents/mb Obsidian Vault/PROJECTS/CODING/X-Thread-Getter - Scraping X (twitter) posts and threads via logged in account.md`
- **Tool inventory entry:** `~/Code/Claude-General/General-Info/installed-tools.md` → x-thread-getter section

## Related Tools

- `xfetch` — simpler Grok-only predecessor, useful as a quick fallback
- `xsearch` — real-time X/web search via Grok API
- `ubm` — bookmark search; x-thread-getter enriches individual threads from ubm results
