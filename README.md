# UBM - Universal Bookmarks Manager

A fast, standalone CLI tool for searching and retrieving bookmarks from multiple sources. Currently supports Twitter bookmarks (via [twitter-web-exporter](https://github.com/prinsss/twitter-web-exporter)) with extensible design for Chrome, Firefox, and other sources.

## Features

- **Fast Search**: SQLite FTS5 full-text search with BM25 ranking
- **AI-Powered Categorisation**: Automatically categorise bookmarks using LLMs (see [CATEGORISER.md](CATEGORISER.md))
- **Source-Agnostic**: Designed to handle bookmarks from multiple platforms
- **Zero Dependencies**: Pure Python with built-in SQLite (except OpenRouter for categorisation)
- **Automatic Deduplication**: Safe to re-import the same files
- **Simple CLI**: Intuitive commands for import, search, and browsing

## Installation

```bash
# Clone the repository
git clone https://github.com/maxbourke/ubm.git
cd ubm

# Make executable
chmod +x ubm.py

# Optional: Symlink to PATH
ln -s "$(pwd)/ubm.py" ~/bin/ubm
```

## Quick Start

```bash
# Quick import: latest Twitter bookmarks from ~/Downloads
ubm x

# Import Twitter bookmarks from specific file
ubm import /path/to/twitter-Bookmarks-xxx.json

# Search for bookmarks
ubm search "machine learning"

# Search by author
ubm search "climate" --author steve

# List recent bookmarks
ubm list

# Show full bookmark details
ubm show 1234567890123456789

# View statistics
ubm stats

# AI Categorisation (requires OPENROUTER_API_KEY)
ubm categorise init --sample-size 500           # Generate hierarchical taxonomy
ubm categorise run --limit 100 --rate-limit 0  # Fast categorisation (paid API)
ubm categorise run --two-call                   # Experimental: free-form + ontology
ubm categorise stats                            # View progress
```

See [CATEGORISER.md](CATEGORISER.md) and [CATEGORISER_ENHANCEMENTS.md](CATEGORISER_ENHANCEMENTS.md) for detailed documentation.

## Commands

### Quick Import (x)

Fast import of the most recent Twitter bookmarks download:

```bash
# Import latest twitter-Bookmarks-*.json from ~/Downloads
ubm x

# Preview without importing
ubm x --dry-run
```

This command automatically finds the most recent `twitter-Bookmarks-*.json` file in your Downloads folder and imports it. Perfect for quickly importing fresh exports from twitter-web-exporter.

### Import

Import Twitter bookmark JSON files from a specific path:

```bash
# Import bookmarks
ubm import <file>

# Preview without importing
ubm import <file> --dry-run
```

**Note**: Imports are idempotent (safe to re-run on the same file). Duplicate bookmarks are automatically detected and skipped.

### Search

Full-text search across all bookmark fields:

```bash
# Basic search (shows bookmark IDs and truncated content)
ubm search "query"

# Filter by author (handle or name)
ubm search "AI" --author karpathy

# Date range filters
ubm search "python" --after 2024-01-01 --before 2024-12-31

# Limit results
ubm search "rust" --limit 20

# Sort by date instead of relevance
ubm search "golang" --order date_desc

# Show full content (not truncated) - great for LLM context
ubm search "claude code" --full --limit 100 > context.txt

# Hide bookmark IDs for cleaner output
ubm search "AI" --full --no-ids > ai_tweets.txt
```

**FTS5 Query Syntax**:
- Phrase search: `"machine learning"`
- Boolean: `AI AND (python OR rust)`
- Prefix: `climat*` (matches climate, climatic, etc.)
- Multiple terms: `python tensorflow` (AND by default)

**Output Modes**:
- **Default**: Compact view with IDs `[1234567890123456789]` and truncated content (80 chars)
- **`--full`**: Complete content with line breaks preserved, URLs included
- **`--no-ids`**: Hide bookmark IDs from output (useful for clean exports)

### List

Browse bookmarks without search:

```bash
# List 20 most recent
ubm list

# List with filters
ubm list --author elonmusk --limit 50

# Pagination
ubm list --limit 20 --offset 40

# Full content mode
ubm list --full --limit 10

# Export author's tweets for LLM context
ubm list --author karpathy --full --no-ids > karpathy_context.txt
```

### Show

Display full bookmark details:

```bash
# Show bookmark by ID
ubm show 1234567890123456789

# JSON output (for scripting)
ubm show 1234567890123456789 --json
```

### Stats

View database statistics:

```bash
ubm stats
```

Displays:
- Total bookmarks count
- Breakdown by source type
- Date range
- Import history
- Database size

### Sources

View import history:

```bash
# Show recent imports
ubm sources

# Show more history
ubm sources --limit 20
```

### Categorise

AI-powered bookmark categorisation with hierarchical taxonomy. See [CATEGORISER.md](CATEGORISER.md) for full documentation.

```bash
# Generate taxonomy from sample
ubm categorise init --sample-size 500 --strategy diverse

# Categorise all uncategorised bookmarks
ubm categorise run

# View statistics
ubm categorise stats

# Display taxonomy tree
ubm categorise list --counts

# Review edge cases
ubm categorise review
```

**Requirements**:
- Set `OPENROUTER_API_KEY` environment variable
- Recommended models: `anthropic/claude-3.5-sonnet` or free tier alternatives

**Note**: Full categorisation of 15K bookmarks takes ~20-25 hours but is resumable if interrupted.

> **Status**: The categorisation feature is functional but has not yet been fully user-tested beyond the initial development environment. Core search and import features are stable.

## Data Location

By default, UBM stores its database in your home directory:

```
~/.ubm/ubm.db
```

**Custom Location**: Set the `UBM_DB_PATH` environment variable to use a different location:

```bash
export UBM_DB_PATH=/custom/path/ubm.db
ubm stats  # Will use custom path
```

The database is automatically created on first run. You can backup this single file to preserve all your bookmarks.

## Current Bookmark Formats: Twitter only

**Note**: Currently, UBM only works with Twitter bookmarks. Use [twitter-web-exporter](https://github.com/prinsss/twitter-web-exporter) to download your Twitter/X bookmarks as JSON files.

UBM expects Twitter bookmark JSON files in the format exported by twitter-web-exporter. The format should be an array of tweet objects with fields like:

```json
[
  {
    "id": "1234567890123456789",
    "created_at": "2023-04-15 17:16:27 +10:00",
    "full_text": "Tweet content here...",
    "url": "https://twitter.com/user/status/...",
    "screen_name": "username",
    "name": "Display Name",
    "favorite_count": 42,
    "retweet_count": 5,
    ...
  }
]
```

## Performance

- **Import Speed**: ~5,000 bookmarks/second
- **Search Speed**: <100ms on 10,000 bookmarks
- **Database Size**: ~2-3 KB per bookmark
  - 1,000 bookmarks ≈ 2-3 MB
  - 10,000 bookmarks ≈ 20-30 MB

## Extending to New Sources

UBM is designed to support multiple bookmark sources. The data model uses:

- **source_type**: Identifies the source (twitter, chrome, firefox, etc.)
- **Flexible schema**: Common fields (url, content, created_at) + source-specific metadata in JSON blob
- **Source-agnostic search**: FTS5 index works across all sources

### Adding a New Importer

The importer uses a simple registry pattern. To add support for a new bookmark source (e.g., Chrome):

**1. Add a detector function** in `ubm/importer.py`:

```python
def _detect_chrome_format(file_path: Path) -> bool:
    """Check if file matches Chrome bookmark export format."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # Check for Chrome-specific structure
            return 'roots' in data and 'bookmark_bar' in data.get('roots', {})
    except (json.JSONDecodeError, KeyError, IOError):
        return False
    return False
```

**2. Add an importer function**:

```python
def _import_chrome_json(file_path: Path, conn: sqlite3.Connection, dry_run: bool = False) -> ImportStats:
    """Import Chrome bookmarks from JSON file."""
    # Parse Chrome bookmark file
    bookmarks = _parse_chrome_bookmarks(file_path)

    # Transform to canonical schema
    transformed = []
    for bm in bookmarks:
        transformed.append({
            'id': bm['id'],  # or generate from URL hash
            'source_type': 'chrome',
            'source_file': str(file_path),
            'imported_at': datetime.now().isoformat(),
            'created_at': bm.get('date_added'),
            'title': bm.get('name'),
            'url': bm['url'],
            'content': bm.get('name', ''),  # Chrome has no content
            'author_handle': None,
            'author_name': None,
            'metadata_json': json.dumps({'folder': bm.get('folder')})
        })

    # Use shared insert logic (similar to _import_twitter_json)
    # ... bulk insert with deduplication ...
```

**3. Register in the dictionaries**:

```python
IMPORT_FUNCTIONS = {
    'twitter': _import_twitter_json,
    'chrome': _import_chrome_json,  # Add this
}

DETECTORS = {
    'twitter': _detect_twitter_format,
    'chrome': _detect_chrome_format,  # Add this
}
```

**4. Update CLI choices** in `ubm.py`:

```python
import_parser.add_argument('--type', dest='source_type',
                          choices=['twitter', 'chrome'],  # Add 'chrome'
                          help='Bookmark source type (auto-detected if not specified)')
```

That's it! The new importer will:
- Auto-detect when importing files
- Work with `ubm import --type chrome file.json`
- Show up in stats with `ubm stats`
- Be fully searchable alongside other sources

## Troubleshooting

### Database locked errors

If you get "database is locked" errors:
- Close any other programs accessing the database
- The database is located at `~/.ubm/ubm.db` (or `$UBM_DB_PATH` if set)

### Import errors

If imports fail:
- Check JSON file is valid: `python3 -m json.tool file.json`
- Use `--dry-run` to preview import without writing
- Ensure the JSON is an array of bookmark objects

### Search returns no results

- Check your query syntax (FTS5 format)
- Try simpler queries first (single words)
- Use `ubm list` to verify bookmarks were imported
- Check filters (--author, --after, --before)

## Development

### Project Structure

```
ubm/
├── ubm.py              # CLI entry point
└── ubm/
    ├── db.py          # Database layer
    ├── importer.py    # Import logic
    ├── search.py      # Search queries
    └── display.py     # Output formatting

Database: ~/.ubm/ubm.db (or $UBM_DB_PATH if set)
```

### Requirements

- Python 3.11+
- No external dependencies (uses built-in SQLite)

## Licence

Personal project by Max Bourke.

## Future Enhancements

- Chrome bookmark import
- Firefox bookmark import
- Raindrop.io import
- Export functionality (JSON, CSV, markdown)
- Tag management
- Browser extension for quick bookmarking
- Web UI for browsing
