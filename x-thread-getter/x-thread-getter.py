#!/usr/bin/env -S uv run --script
# /// script
# dependencies = ["openai", "twitter-api-client", "browser-cookie3", "playwright"]
# ///
"""
threadgetter - Fetch a full X.com tweet thread as markdown + JSON.

Usage:
    threadgetter <url>                  # Save MD + JSON to default dir (free method)
    threadgetter <url> --grok           # Force Grok API (costs money, more reliable)
    threadgetter <url> -o DIR           # Save to custom directory
    threadgetter <url> --md-only        # Save markdown only
    threadgetter <url> --json-only      # Save JSON only
    threadgetter <url> --stdout         # Print markdown to stdout, no files

Default fetch method: twitter-api-client + browser-cookie3 (free, uses Chrome session).
Fallback/override: Grok API (requires XAI_API_KEY, ~$0.02/call).
"""

import argparse
import json
import os
import re
import sys
from datetime import date
from pathlib import Path

DEFAULT_DIR = Path("/Users/maxbourke/Documents/mb Obsidian Vault/Clippings/X.com Clippings")
XAI_API_KEY = os.environ.get("XAI_API_KEY") or os.environ.get("LLM_API_KEY")
GROK_MODEL = "grok-4"


def extract_username(url: str) -> str:
    match = re.search(r"(?:x|twitter)\.com/([^/]+)/status/", url)
    return match.group(1) if match else "unknown"


def extract_tweet_id(url: str) -> str:
    match = re.search(r"/status/(\d+)", url)
    return match.group(1) if match else None


def is_article_url(url: str) -> bool:
    return bool(re.search(r"x\.com/(?:i/article|\w+/article)/\d+", url))


# ── X Article method: Playwright + Chrome profile ───────────────────────────

def fetch_article_playwright(url: str) -> dict:
    """Fetch an X Article using Playwright with cookies from Chrome session."""
    import browser_cookie3
    from playwright.sync_api import sync_playwright

    # Extract auth cookies from Chrome (same approach as free thread method)
    jar = browser_cookie3.chrome(domain_name='.x.com')
    cookies = [
        {"name": c.name, "value": c.value, "domain": ".x.com", "path": "/"}
        for c in jar
        if c.name in ('auth_token', 'ct0', 'twid', 'kdt', 'guest_id')
    ]

    if not any(c["name"] == "auth_token" for c in cookies):
        raise RuntimeError("auth_token not found in Chrome cookies — are you logged in to x.com in Chrome?")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, channel="chrome")
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
        )
        context.add_cookies(cookies)
        page = context.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=30000)

        # Wait for article body to appear
        try:
            page.wait_for_selector('[data-testid="article-body"], article', timeout=15000)
        except Exception:
            pass

        # Extract text — prefer article-body testid, fall back to main
        text = page.evaluate("""() => {
            const specific = document.querySelector('[data-testid="article-body"]');
            if (specific) return specific.innerText;
            const art = document.querySelector('article');
            if (art) return art.innerText;
            const main = document.querySelector('main');
            return main ? main.innerText : document.body.innerText;
        }""")

        # Try to get title from page <title>, then from first line of article text
        raw_title = page.title().replace(" | X", "").strip()
        raw_title = re.sub(r"^\(\d+\)\s*", "", raw_title)
        if raw_title in ("X", "", "Twitter"):
            # Fall back to first non-empty line of article text
            first_line = next((l.strip() for l in text.splitlines() if l.strip()), "X Article")
            title = first_line[:100]
        else:
            title = raw_title

        # Try to get author from URL (x.com/<user>/article/<id>) or from page
        author_match = re.search(r"x\.com/(?!i/)(@?\w+)/article/", url)
        if author_match:
            author = f"@{author_match.group(1)}"
        else:
            # x.com/i/article/<id> — try to extract from page after redirect
            final_url = page.url
            redirected_match = re.search(r"x\.com/(?!i/)(\w+)/article/", final_url)
            author = f"@{redirected_match.group(1)}" if redirected_match else "@unknown"

        browser.close()

    return {"title": title, "author": author, "text": text.strip(), "url": url}


def format_article_text(title: str, author: str, raw: str) -> str:
    """Clean up innerText scraped from an X Article page."""
    lines = raw.splitlines()

    # ── Strip header block ─────────────────────────────────────────────────
    # The page starts with: title, author display name, @handle, ·, date,
    # Follow, engagement counts (digits / "2.8K" etc.), and optional
    # "Subscribe on Substack." — all before the real article body begins.
    header_patterns = [
        re.compile(r"^\s*$"),                          # blank
        re.compile(r"^·$"),                            # separator dot
        re.compile(r"^Follow$"),
        re.compile(r"^Subscribe\s+on\s+\w+\.$", re.I),
        re.compile(r"^\d+(\.\d+)?[KkMm]?$"),          # engagement counts
        re.compile(r"^[A-Z][a-z]+ \d{1,2}$"),         # "Jun 1" style date
        re.compile(r"^@\w+$"),                         # @handle
    ]

    # Also skip lines that exactly match title or author display name
    title_norm = title.strip().lower()
    author_norm = author.lstrip("@").lower()

    def is_header_noise(line: str) -> bool:
        s = line.strip()
        if s.lower() == title_norm:
            return True
        if s.lower() == author_norm:
            return True
        return any(p.match(s) for p in header_patterns)

    # Find where real body starts: first line that's NOT header noise and
    # is longer than ~30 chars (i.e. a real sentence)
    body_start = 0
    for i, line in enumerate(lines):
        s = line.strip()
        if not is_header_noise(line) and len(s) > 30:
            body_start = i
            break

    lines = lines[body_start:]

    # ── Strip known boilerplate lines anywhere in body ────────────────────
    boilerplate = re.compile(r"^Subscribe\s+on\s+\w+\.\s*$", re.I)
    lines = [l for l in lines if not boilerplate.match(l.strip())]

    # ── Strip footer block ─────────────────────────────────────────────────
    footer_triggers = [
        "Want to publish your own Article?",
        "Upgrade to Premium",
    ]
    for i, line in enumerate(lines):
        if any(line.strip().startswith(t) for t in footer_triggers):
            lines = lines[:i]
            break

    # ── Detect and mark section headings ──────────────────────────────────
    # A heading is a short line (≤80 chars) that:
    #   - doesn't end with sentence-ending punctuation
    #   - isn't all-caps (those are usually UI noise)
    #   - is followed by a longer body line
    result = []
    for i, line in enumerate(lines):
        s = line.strip()
        next_s = lines[i + 1].strip() if i + 1 < len(lines) else ""
        is_heading = (
            s
            and len(s) <= 80
            and not s[-1] in ".!?,;:)"
            and not s.isupper()
            and len(next_s) > 60  # followed by real paragraph
        )
        if is_heading:
            if result and result[-1] != "":
                result.append("")
            result.append(f"## {s}")
            result.append("")
        else:
            result.append(line)

    # ── Add blank lines between paragraphs ───────────────────────────────
    spaced = []
    for i, line in enumerate(result):
        spaced.append(line)
        s = line.strip()
        next_s = result[i + 1].strip() if i + 1 < len(result) else ""
        # Insert blank line between two non-empty, non-heading lines
        if s and next_s and not s.startswith("#") and not next_s.startswith("#"):
            spaced.append("")
    result = spaced

    # ── Collapse excessive blank lines ────────────────────────────────────
    cleaned = []
    prev_blank = False
    for line in result:
        is_blank = not line.strip()
        if is_blank and prev_blank:
            continue
        cleaned.append(line)
        prev_blank = is_blank

    return "\n".join(cleaned).strip()


def build_output_article(data: dict) -> tuple[dict, str]:
    """Build JSON + markdown from a fetched X Article."""
    today = date.today().isoformat()
    title = data.get("title", "X Article")
    author = data.get("author", "@unknown")
    url = data.get("url", "")
    text = format_article_text(title, author, data.get("text", ""))

    full = {
        "url": url,
        "author": author,
        "fetched": today,
        "title": title,
        "type": "x-article",
        "text": text,
    }

    md_lines = [
        "---",
        f"source: {url}",
        f'author: "{author}"',
        f"fetched: {today}",
        f'title: "{title}"',
        "tags:",
        "  - clipping",
        "  - x-article",
        "---",
        "",
        f"# {title}",
        "",
        text,
        "",
    ]

    return full, "\n".join(md_lines)


# ── Free method: twitter-api-client + browser-cookie3 ──────────────────────

def fetch_thread_free(tweet_id: str) -> list[dict]:
    """Fetch thread via Twitter's internal GraphQL API using Chrome session cookies."""
    import browser_cookie3
    from twitter.scraper import Scraper

    jar = browser_cookie3.chrome(domain_name='.x.com')
    cookies = {c.name: c.value for c in jar if c.name in ('auth_token', 'ct0')}

    if not cookies.get('auth_token'):
        raise RuntimeError("auth_token not found in Chrome cookies — are you logged in to x.com in Chrome?")

    scraper = Scraper(cookies=cookies, pbar=False)
    results = scraper.tweets_details([int(tweet_id)])
    return results


def parse_thread_from_graphql(results: list, focal_tweet_id: str) -> list[dict]:
    """Extract ordered thread tweets from tweets_details() response."""
    import html as html_mod

    def find_tweet_entries(obj):
        entries = []
        if isinstance(obj, dict):
            typename = obj.get('__typename')

            # Silently skip tombstoned/unavailable slots — no legacy data present
            if typename in ('TweetTombstone', 'TweetUnavailable'):
                return entries

            if typename in ('Tweet', 'TweetWithVisibilityResults'):
                tweet = obj if typename == 'Tweet' else obj.get('tweet', obj)
                legacy = tweet.get('legacy', {})
                if not legacy:
                    # Empty result slot — skip
                    for v in obj.values():
                        entries.extend(find_tweet_entries(v))
                    return entries

                core = tweet.get('core', {})
                user = core.get('user_results', {}).get('result', {}).get('legacy', {})

                if legacy.get('full_text'):
                    # Extract media items from extended_entities
                    media_items = []
                    for m in legacy.get('extended_entities', {}).get('media', []):
                        mtype = m.get('type', 'photo')
                        if mtype == 'photo':
                            media_items.append({
                                'type': 'image',
                                'url': m.get('media_url_https', ''),
                            })
                        elif mtype in ('video', 'animated_gif'):
                            variants = m.get('video_info', {}).get('variants', [])
                            mp4s = [v for v in variants if v.get('content_type') == 'video/mp4']
                            best = max(mp4s, key=lambda v: v.get('bitrate', 0)) if mp4s else (variants[0] if variants else {})
                            media_items.append({
                                'type': mtype,
                                'url': best.get('url', ''),
                            })

                    raw_text = legacy.get('full_text', '')
                    is_article_link = False
                    is_retweet = False

                    # ── Note tweet (long-form >280 chars) ──────────────────
                    # full_text is truncated; real text is in note_tweet subtree
                    note_result = (
                        tweet.get('note_tweet', {})
                        .get('note_tweet_results', {})
                        .get('result', {})
                    )
                    note_text = note_result.get('text', '')
                    note_entities = note_result.get('entity_set', {})

                    if note_text:
                        raw_text = note_text
                        url_expansions = {
                            u['url']: u.get('expanded_url', u['url'])
                            for u in note_entities.get('urls', [])
                            if u.get('url') and u.get('expanded_url')
                        }
                    else:
                        # Collect t.co → expanded URL map from legacy entities
                        url_expansions = {
                            u['url']: u.get('expanded_url', u['url'])
                            for u in legacy.get('entities', {}).get('urls', [])
                            if u.get('url') and u.get('expanded_url')
                        }

                    # ── X Article ──────────────────────────────────────────
                    # full_text is a bare t.co URL; body lives in article subtree
                    article_result = (
                        tweet.get('article', {})
                        .get('article_results', {})
                        .get('result', {})
                    )
                    tco_only = bool(re.fullmatch(r'https://t\.co/\S+', raw_text.strip()))

                    if tco_only and article_result:
                        # Prefer the article's plain_text body if available
                        plain_text = article_result.get('plain_text', '')
                        if plain_text:
                            raw_text = plain_text
                            url_expansions = {}  # plain_text has real URLs already
                        else:
                            # Fall back to expanding the t.co to the article URL
                            raw_text = url_expansions.get(raw_text.strip(), raw_text.strip())
                        is_article_link = True
                    elif tco_only and not note_text:
                        # Bare t.co with no article and no note — just expand the URL
                        raw_text = url_expansions.get(raw_text.strip(), raw_text.strip())
                        is_article_link = True

                    # ── Retweet ────────────────────────────────────────────
                    # full_text is truncated "RT @handle: …"; real text is in
                    # retweeted_status_result. We leave RT tweets in the entry
                    # list so thread ordering is preserved, but flag them.
                    rt_result = legacy.get('retweeted_status_result', {})
                    if raw_text.startswith('RT @') and rt_result:
                        is_retweet = True
                        rt_obj = rt_result.get('result', {})
                        if rt_obj.get('__typename') == 'TweetWithVisibilityResults':
                            rt_obj = rt_obj.get('tweet', rt_obj)
                        rt_legacy = rt_obj.get('legacy', {})
                        rt_note = (
                            rt_obj.get('note_tweet', {})
                            .get('note_tweet_results', {})
                            .get('result', {})
                        )
                        rt_text = rt_note.get('text') or rt_legacy.get('full_text', raw_text)
                        rt_url_exp = {
                            u['url']: u.get('expanded_url', u['url'])
                            for u in rt_legacy.get('entities', {}).get('urls', [])
                            if u.get('url') and u.get('expanded_url')
                        }
                        raw_text = rt_text
                        url_expansions = rt_url_exp

                    # ── Text cleanup ───────────────────────────────────────
                    # HTML-entity decode (full_text uses &amp; &lt; &gt; etc.)
                    text = html_mod.unescape(raw_text)

                    if not is_article_link and not is_retweet:
                        # Strip trailing t.co URL (represents attached card/media)
                        text = re.sub(r'\s*https://t\.co/\S+$', '', text).strip()

                    # Expand remaining t.co URLs inline
                    for tco, expanded in url_expansions.items():
                        text = text.replace(tco, expanded)

                    # ── Quoted tweet ───────────────────────────────────────
                    quoted = None
                    qt_result = tweet.get('quoted_status_result', {}).get('result', {})
                    if qt_result:
                        if qt_result.get('__typename') == 'TweetWithVisibilityResults':
                            qt_result = qt_result.get('tweet', qt_result)
                        qt_legacy = qt_result.get('legacy', {})
                        qt_core = qt_result.get('core', {})
                        qt_user = qt_core.get('user_results', {}).get('result', {}).get('legacy', {})
                        qt_note = (
                            qt_result.get('note_tweet', {})
                            .get('note_tweet_results', {})
                            .get('result', {})
                        )
                        qt_raw = qt_note.get('text') or qt_legacy.get('full_text', '')
                        qt_url_exp = {
                            u['url']: u.get('expanded_url', u['url'])
                            for u in qt_legacy.get('entities', {}).get('urls', [])
                            if u.get('url') and u.get('expanded_url')
                        }
                        qt_raw = re.sub(r'\s*https://t\.co/\S+$', '', qt_raw).strip()
                        for tco, expanded in qt_url_exp.items():
                            qt_raw = qt_raw.replace(tco, expanded)
                        qt_media = []
                        for m in qt_legacy.get('extended_entities', {}).get('media', []):
                            mtype = m.get('type', 'photo')
                            if mtype == 'photo':
                                qt_media.append({'type': 'image', 'url': m.get('media_url_https', '')})
                        if qt_raw:
                            quoted = {
                                'author': qt_user.get('screen_name', 'unknown'),
                                'author_name': qt_user.get('name', ''),
                                'created_at': qt_legacy.get('created_at', ''),
                                'text': html_mod.unescape(qt_raw),
                                'media': qt_media,
                            }

                    entries.append({
                        'id': legacy.get('id_str', ''),
                        'text': text,
                        'author': user.get('screen_name', 'unknown'),
                        'author_name': user.get('name', ''),
                        'created_at': legacy.get('created_at', ''),
                        'in_reply_to': legacy.get('in_reply_to_status_id_str'),
                        'quoted_tweet': quoted,
                        'media': media_items,
                        'is_article_link': is_article_link,
                        'is_retweet': is_retweet,
                        'is_note_tweet': bool(note_text),
                    })
            for v in obj.values():
                entries.extend(find_tweet_entries(v))
        elif isinstance(obj, list):
            for item in obj:
                entries.extend(find_tweet_entries(item))
        return entries

    all_entries = find_tweet_entries(results)

    # Deduplicate by id
    seen = {}
    for e in all_entries:
        if e['id'] not in seen:
            seen[e['id']] = e

    # Build thread: start from focal tweet, follow reply chain
    tweet_map = seen
    focal = tweet_map.get(focal_tweet_id)
    if not focal:
        # Fallback: return all tweets by focal author sorted by id
        focal_author = None
        for e in tweet_map.values():
            if e['id'] == focal_tweet_id:
                focal_author = e['author']
                break
        if not focal_author and tweet_map:
            # Use most common author
            from collections import Counter
            focal_author = Counter(e['author'] for e in tweet_map.values()).most_common(1)[0][0]
        thread = sorted(
            [e for e in tweet_map.values() if e['author'] == focal_author],
            key=lambda x: x['id']
        )
        return thread

    # Follow the reply chain from focal tweet forward only
    # Tweet IDs are snowflake IDs — numerically chronological, so
    # anything with id < focal_tweet_id came before and should be excluded.
    focal_author = focal['author']
    thread = [
        e for e in tweet_map.values()
        if e['author'] == focal_author and int(e['id']) >= int(focal_tweet_id)
    ]
    thread = sorted(thread, key=lambda x: int(x['id']))
    return thread


# ── Grok API method ─────────────────────────────────────────────────────────

GROK_SYSTEM_PROMPT = """\
You are a precise data extractor. When given an X.com tweet thread URL, return the full \
thread as a JSON object with this exact schema:

{
  "author": "@handle",
  "tweets": [
    {
      "position": 1,
      "text": "full tweet text",
      "quoted_tweet": null
    },
    {
      "position": 2,
      "text": "full tweet text",
      "quoted_tweet": {
        "url": "https://x.com/...",
        "author": "@handle",
        "text": "full quoted tweet text"
      }
    }
  ]
}

Rules:
- Include every tweet in the thread in order, do not skip any.
- For quoted tweets, fetch and include the full text of the quoted tweet inline.
- If a tweet has no quoted tweet, set "quoted_tweet" to null.
- Return ONLY the JSON object, no other text, no markdown code fences.
"""


def fetch_thread_grok(url: str) -> dict:
    """Fetch thread via Grok API. Returns structured dict."""
    from openai import OpenAI

    if not XAI_API_KEY:
        raise RuntimeError("XAI_API_KEY or LLM_API_KEY not set")

    client = OpenAI(api_key=XAI_API_KEY, base_url="https://api.x.ai/v1")
    response = client.responses.create(
        model=GROK_MODEL,
        tools=[{"type": "x_search"}],
        instructions=GROK_SYSTEM_PROMPT,
        input=f"Fetch the full thread: {url}",
    )

    raw = ""
    for item in response.output:
        if item.type == "message":
            for content in item.content:
                if hasattr(content, "text"):
                    raw = content.text.strip()
                    break

    if not raw:
        raise RuntimeError("No response from Grok API")

    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    return json.loads(raw)


# ── Output builders ──────────────────────────────────────────────────────────

def slugify(text: str, max_len: int = 60) -> str:
    first_line = text.strip().split("\n")[0][:200]
    first_line = re.sub(r"@\w+\s*", "", first_line)
    first_line = re.sub(r"^//\s*", "", first_line).strip()
    title = re.sub(r'[\\/:*?"<>|]', "", first_line)
    title = re.sub(r"\s+", " ", title).strip()
    return title[:max_len].rstrip(" .,–-")


def format_tweet_timestamp(created_at: str) -> str:
    """Convert Twitter's created_at string to 'YYYY-MM-DD HH:MM' (Sydney time)."""
    if not created_at:
        return ""
    try:
        from datetime import timezone, timedelta
        import email.utils
        dt_utc = email.utils.parsedate_to_datetime(created_at)
        sydney = timezone(timedelta(hours=10))  # AEST; close enough for display
        dt_local = dt_utc.astimezone(sydney)
        return dt_local.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return created_at


def build_output_free(url: str, thread: list[dict]) -> tuple[dict, str]:
    """Build JSON + markdown from free-method thread list."""
    author = f"@{thread[0]['author']}" if thread else "@unknown"
    today = date.today().isoformat()

    tweets_json = [
        {
            "position": i + 1,
            "id": t['id'],
            "text": t['text'],
            "author": t.get('author', ''),
            "author_name": t.get('author_name', ''),
            "created_at": t.get('created_at', ''),
            "media": t.get('media', []),
            "quoted_tweet": t.get('quoted_tweet'),
            "is_article_link": t.get('is_article_link', False),
            "is_retweet": t.get('is_retweet', False),
            "is_note_tweet": t.get('is_note_tweet', False),
        }
        for i, t in enumerate(thread)
    ]

    full = {
        "url": url,
        "author": author,
        "fetched": today,
        "tweet_count": len(tweets_json),
        "tweets": tweets_json,
    }

    md_lines = [
        "---",
        f"source: {url}",
        f'author: "{author}"',
        f"fetched: {today}",
        f"tweet_count: {len(tweets_json)}",
        "tags:",
        "  - clipping",
        "  - x-thread",
        "---",
    ]

    for idx, tweet in enumerate(tweets_json):
        # ── Header line ───────────────────────────────────────────────────
        name = tweet.get('author_name') or tweet.get('author', '')
        handle = tweet.get('author', '')
        ts = format_tweet_timestamp(tweet.get('created_at', ''))
        tweet_id = tweet.get('id', '')
        tweet_url = f"https://x.com/{handle}/status/{tweet_id}" if tweet_id else ""
        ts_part = f"[{ts}]({tweet_url})" if (ts and tweet_url) else ts
        flags = []
        if tweet.get('is_note_tweet'):
            flags.append("Note Tweet")
        if tweet.get('is_retweet'):
            flags.append("Retweet")
        flag_str = f" *({', '.join(flags)})*" if flags else ""
        header = f"**{name} (@{handle})**{flag_str} · {ts_part}" if ts_part else f"**{name} (@{handle})**{flag_str}"
        if idx > 0:
            md_lines.append("---")
            md_lines.append("")
        md_lines.append(header)
        md_lines.append("")

        # ── Body ──────────────────────────────────────────────────────────
        if tweet.get('is_article_link') and tweet['text'].startswith('http'):
            article_url = tweet['text'].strip()
            if is_article_url(article_url):
                print(f"  Fetching embedded X Article: {article_url}", file=sys.stderr)
                try:
                    art_data = fetch_article_playwright(article_url)
                    # Prefer the embedded article's headline for the filename slug
                    if art_data.get('title') and not full.get('article_title'):
                        full['article_title'] = art_data['title']
                    art_body = format_article_text(art_data['title'], art_data['author'], art_data['text'])
                    md_lines.append(f"**X Article: [{art_data['title']}]({article_url})**")
                    md_lines.append("")
                    md_lines.append(art_body)
                except Exception as e:
                    print(f"  Warning: could not fetch article: {e}", file=sys.stderr)
                    md_lines.append(f"**X Article** (fetch failed): {article_url}")
            else:
                md_lines.append(f"**Linked post:** {article_url}")
        else:
            md_lines.append(tweet['text'])

        # ── Media ─────────────────────────────────────────────────────────
        for m in tweet.get('media', []):
            if m['type'] == 'image':
                md_lines.append("")
                md_lines.append(f"![]({m['url']})")
            else:
                md_lines.append("")
                md_lines.append(f"[{m['type'].title()}]({m['url']})")

        # ── Quoted tweet ──────────────────────────────────────────────────
        qt = tweet.get('quoted_tweet')
        if qt:
            qt_name = qt.get('author_name') or qt.get('author', '')
            qt_handle = qt.get('author', '')
            qt_ts = format_tweet_timestamp(qt.get('created_at', ''))
            qt_header = f"**{qt_name} (@{qt_handle})** · {qt_ts}" if qt_ts else f"**{qt_name} (@{qt_handle})**"
            md_lines.append("")
            md_lines.append(f"> *Quoted tweet:*")
            md_lines.append(f"> {qt_header}")
            md_lines.append(">")
            for line in qt['text'].splitlines():
                md_lines.append(f"> {line}" if line.strip() else ">")
            for m in qt.get('media', []):
                if m['type'] == 'image':
                    md_lines.append(f"> ![]({m['url']})")

        md_lines.append("")

    return full, "\n".join(md_lines)


def build_output_grok(url: str, data: dict) -> tuple[dict, str]:
    """Build JSON + markdown from Grok-method response dict."""
    author = data.get("author", "@unknown")
    today = date.today().isoformat()
    tweets = data.get("tweets", [])

    full = {
        "url": url,
        "author": author,
        "fetched": today,
        "tweet_count": len(tweets),
        "tweets": tweets,
    }

    md_lines = [
        f"---",
        f"source: {url}",
        f'author: "{author}"',
        f"fetched: {today}",
        f"tweet_count: {len(tweets)}",
        f"tags:",
        f"  - clipping",
        f"  - x-thread",
        f"---",
        f"",
    ]
    for tweet in tweets:
        md_lines.append(tweet.get('text', ''))
        quoted = tweet.get('quoted_tweet')
        if quoted:
            q_author = quoted.get('author', '')
            q_text = quoted.get('text', '')
            q_url = quoted.get('url', '')
            md_lines.append(f"")
            md_lines.append(f"> **{q_author}:** {q_text}")
            if q_url:
                md_lines.append(f"> *(quoted from {q_url})*")
        md_lines.append("")

    return full, "\n".join(md_lines)


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Fetch a full X.com thread as MD + JSON")
    parser.add_argument("url", help="X.com tweet URL")
    parser.add_argument("-o", "--output", help="Output directory (default: Obsidian Clippings)")
    parser.add_argument("--grok", action="store_true", help="Force Grok API (costs money; also fetches quoted tweets)")
    parser.add_argument("--md-only", action="store_true", help="Save markdown only")
    parser.add_argument("--json-only", action="store_true", help="Save JSON only")
    parser.add_argument("--stdout", action="store_true", help="Print markdown to stdout, no files saved")
    args = parser.parse_args()

    # ── X Article URLs ────────────────────────────────────────────────────────
    if is_article_url(args.url):
        print(f"Detected X Article URL — fetching via Playwright...", file=sys.stderr)
        data = fetch_article_playwright(args.url)
        full, markdown = build_output_article(data)
        print(f"Fetched article: {data.get('title', '(no title)')}", file=sys.stderr)

        if args.stdout:
            print(markdown)
            return

        out_dir = Path(args.output) if args.output else DEFAULT_DIR
        out_dir.mkdir(parents=True, exist_ok=True)

        username = data["author"].lstrip("@")
        today = date.today().isoformat()
        slug = slugify(data.get("title", "article"))
        base_name = f"{today} @{username} - {slug}"

        if not args.json_only:
            md_path = out_dir / f"{base_name}.md"
            md_path.write_text(markdown, encoding="utf-8")
            print(f"Saved MD:   {md_path}", file=sys.stderr)

        if not args.md_only:
            json_path = out_dir / f"{base_name}.json"
            json_path.write_text(json.dumps(full, indent=2, ensure_ascii=False), encoding="utf-8")
            print(f"Saved JSON: {json_path}", file=sys.stderr)
        return

    tweet_id = extract_tweet_id(args.url)
    if not tweet_id:
        print(f"Error: could not parse tweet ID from URL: {args.url}", file=sys.stderr)
        sys.exit(1)

    if args.grok:
        print(f"Fetching thread via Grok API (paid)...", file=sys.stderr)
        data = fetch_thread_grok(args.url)
        full, markdown = build_output_grok(args.url, data)
    else:
        print(f"Fetching thread via Twitter internal API (free)...", file=sys.stderr)
        try:
            results = fetch_thread_free(tweet_id)
            thread = parse_thread_from_graphql(results, tweet_id)
            if not thread:
                raise RuntimeError("No tweets extracted from response")
            full, markdown = build_output_free(args.url, thread)
        except Exception as e:
            print(f"Free method failed: {e}", file=sys.stderr)
            if XAI_API_KEY:
                print("Falling back to Grok API...", file=sys.stderr)
                data = fetch_thread_grok(args.url)
                full, markdown = build_output_grok(args.url, data)
            else:
                print("Set XAI_API_KEY to enable Grok fallback.", file=sys.stderr)
                sys.exit(1)

    print(f"Got {full['tweet_count']} tweets from {full['author']}", file=sys.stderr)

    if args.stdout:
        print(markdown)
        return

    out_dir = Path(args.output) if args.output else DEFAULT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    username = full["author"].lstrip("@")
    today = date.today().isoformat()
    # Prefer an embedded X Article headline (captured during article fetch);
    # otherwise fall back to the first non-article tweet's text.
    slug_source = full.get("article_title", "")
    if not slug_source:
        for t in full["tweets"]:
            if not t.get("is_article_link") and t.get("text"):
                slug_source = t["text"]
                break
    slug = slugify(slug_source)
    base_name = f"{today} @{username} - {slug}"

    if not args.json_only:
        md_path = out_dir / f"{base_name}.md"
        md_path.write_text(markdown, encoding="utf-8")
        print(f"Saved MD:   {md_path}", file=sys.stderr)

    if not args.md_only:
        json_path = out_dir / f"{base_name}.json"
        json_path.write_text(json.dumps(full, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Saved JSON: {json_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
