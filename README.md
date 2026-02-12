# UBM - Universal Bookmarks Manager

A fast, standalone CLI tool for searching and retrieving bookmarks from multiple sources. Currently supports Twitter bookmarks (via [twitter-web-exporter](https://github.com/prinsss/twitter-web-exporter)) with extensible design for Chrome, Firefox, and other sources.

## Features

- **Fast Search**: SQLite FTS5 full-text search with BM25 ranking
- **Source-Agnostic**: Designed to handle bookmarks from multiple platforms
- **Zero Dependencies**: Pure Python with built-in SQLite
- **Automatic Deduplication**: Safe to re-import the same files
- **Simple CLI**: Intuitive commands for import, search, and browsing

## Installation

```bash
# Clone or navigate to the project
cd /Users/maxbourke/Code/ubm

# Make executable
chmod +x ubm.py

# Optional: Symlink to PATH
ln -s "$(pwd)/ubm.py" ~/bin/ubm
```

## Quick Start

```bash
# Import Twitter bookmarks
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
```

## Commands

### Import

Import Twitter bookmark JSON files:

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

## Data Location

All data is stored in:

```
/Users/maxbourke/Code/ubm/data/ubm.db
```

The database is automatically created on first run. You can backup this single file to preserve all your bookmarks.

## Twitter Bookmark Format

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

To add a new source:

1. Add importer function in `ubm/importer.py`
2. Map source fields to canonical schema
3. Set `source_type` appropriately
4. Store source-specific data in `metadata_json`

## Troubleshooting

### Database locked errors

If you get "database is locked" errors:
- Close any other programs accessing the database
- The database is located at `/Users/maxbourke/Code/ubm/data/ubm.db`

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
├── ubm/
│   ├── db.py          # Database layer
│   ├── importer.py    # Import logic
│   ├── search.py      # Search queries
│   └── display.py     # Output formatting
└── data/
    └── ubm.db         # SQLite database
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
